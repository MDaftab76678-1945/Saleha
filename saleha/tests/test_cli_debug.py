import tempfile
import unittest
import json
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from saleha.agents.base_agent import AgentResponse
from saleha.agents.debugger import DebugResult
from saleha.cli.commands import cli


class FakeDebugger:
    last_instance = None

    def __init__(self, model="auto"):
        FakeDebugger.last_instance = self
        self.error_log = None

    def debug_code(self, task, code, error_log):
        self.error_log = error_log
        return DebugResult(
            success=True,
            diagnosis="Fixed the undefined variable.",
            fixed_code="print('fixed')",
            model_used="test-model",
        )


class DebugCliTests(unittest.TestCase):
    def test_requires_exactly_one_error_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "broken.py"
            code_path.write_text("print('broken')", encoding="utf-8")
            result = CliRunner().invoke(cli, ["debug", str(code_path)])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Provide either ERROR_LOG or --error-file", result.output)

    def test_save_and_output_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "broken.py"
            code_path.write_text("print('broken')", encoding="utf-8")
            result = CliRunner().invoke(cli, [
                "debug", str(code_path), "SyntaxError", "--save", "--output", str(Path(tmp) / "fixed.py")
            ])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Use either --save or --output", result.output)

    def test_output_writes_validated_code_to_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "broken.py"
            output_path = Path(tmp) / "fixed.py"
            code_path.write_text("print('broken')", encoding="utf-8")

            with patch("saleha.cli.commands.DebuggerAgent", FakeDebugger):
                result = CliRunner().invoke(cli, [
                    "debug", str(code_path), "NameError", "--output", str(output_path)
                ])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "print('fixed')\n")
            self.assertEqual(code_path.read_text(encoding="utf-8"), "print('broken')")

    def test_error_file_is_read_as_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "broken.py"
            error_path = Path(tmp) / "traceback.txt"
            code_path.write_text("print('broken')", encoding="utf-8")
            error_path.write_text("Traceback (most recent call last):\nNameError: x", encoding="utf-8")

            with patch("saleha.cli.commands.DebuggerAgent", FakeDebugger):
                result = CliRunner().invoke(cli, [
                    "debug", str(code_path), "--error-file", str(error_path)
                ])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(FakeDebugger.last_instance.error_log,
                             "Traceback (most recent call last):\nNameError: x")

    def test_debug_json_returns_clean_machine_readable_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "broken.py"
            code_path.write_text("print('broken')", encoding="utf-8")

            with patch("saleha.cli.commands.DebuggerAgent", FakeDebugger):
                result = CliRunner().invoke(cli, [
                    "debug", str(code_path), "NameError", "--json"
                ])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["fixed_code"], "print('fixed')")
        self.assertEqual(payload["saved_to"], "")

    def test_ask_prints_one_shot_response(self):
        response = AgentResponse(success=True, content="Hello from Saleha")
        with patch("saleha.cli.commands.BaseAgent") as agent_class:
            agent_class.return_value.think.return_value = response
            result = CliRunner().invoke(cli, ["ask", "Say hello"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Hello from Saleha", result.output)
        agent_class.return_value.think.assert_called_once_with("Say hello")

    def test_ask_json_returns_machine_readable_response(self):
        response = AgentResponse(success=True, content="Hello from Saleha", model_used="test-model")
        with patch("saleha.cli.commands.BaseAgent") as agent_class:
            agent_class.return_value.think.return_value = response
            result = CliRunner().invoke(cli, ["ask", "Say hello", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["content"], "Hello from Saleha")
        self.assertEqual(payload["model_used"], "test-model")

    def test_run_json_returns_clean_pipeline_result(self):
        fake_result = SimpleNamespace(
            success=True,
            final_code="print('done')",
            attempts=1,
            log="pipeline complete",
        )
        with patch("saleha.cli.commands.SalehaOrchestrator") as orchestrator_class:
            orchestrator_class.return_value.execute_task.return_value = fake_result
            result = CliRunner().invoke(cli, ["run", "Create a script", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["final_code"], "print('done')")
        self.assertEqual(payload["attempts"], 1)
        self.assertEqual(payload["log"], "pipeline complete")

    def test_models_json_returns_model_inventory(self):
        result = CliRunner().invoke(cli, ["models", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn("models", payload)
        self.assertIn("qwen2.5-coder:1.5b", payload["models"])

    def test_skills_json_returns_registered_skills(self):
        result = CliRunner().invoke(cli, ["skills", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn("skills", payload)
        self.assertIn("calculator", [skill["name"] for skill in payload["skills"]])

    def test_history_json_returns_task_collection(self):
        result = CliRunner().invoke(cli, ["history", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn("tasks", payload)
        self.assertIsInstance(payload["tasks"], list)

    def test_stats_json_returns_stats_collection(self):
        result = CliRunner().invoke(cli, ["stats", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["task_type"], "coding")
        self.assertIsInstance(payload["models"], (dict, list))

    def test_audit_json_returns_record_collection(self):
        result = CliRunner().invoke(cli, ["audit", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn("records", payload)
        self.assertIsInstance(payload["records"], list)

    def test_test_json_returns_clean_validation_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "valid.py"
            code_path.write_text("print('ok')", encoding="utf-8")
            result = CliRunner().invoke(cli, ["test", str(code_path), "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["error_type"], "None")

    def test_plan_json_returns_steps_and_recommendation(self):
        fake_plan = SimpleNamespace(
            success=True,
            steps=["Create the module", "Add tests"],
            recommendation="BREAK_DOWN",
            raw_response="",
        )
        with patch("saleha.cli.commands.PlannerAgent") as planner_class:
            planner_class.return_value.create_plan.return_value = fake_plan
            result = CliRunner().invoke(cli, ["plan", "Build a module", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["steps"], ["Create the module", "Add tests"])
        self.assertEqual(payload["recommendation"], "BREAK_DOWN")

    def test_code_json_returns_generated_code(self):
        fake_code = SimpleNamespace(
            success=True,
            code="print('generated')",
            error="",
            attempts=1,
            model_used="test-model",
        )
        with patch("saleha.cli.commands.CoderAgent") as coder_class:
            coder_class.return_value.generate_code.return_value = fake_code
            result = CliRunner().invoke(cli, ["code", "Create a script", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["code"], "print('generated')")
        self.assertEqual(payload["model_used"], "test-model")

    def test_code_output_writes_generated_code(self):
        fake_code = SimpleNamespace(
            success=True, code="print('generated')", error="", attempts=1, model_used="test-model"
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "generated.py"
            with patch("saleha.cli.commands.CoderAgent") as coder_class:
                coder_class.return_value.generate_code.return_value = fake_code
                result = CliRunner().invoke(cli, [
                    "code", "Create a script", "--output", str(output_path), "--json"
                ])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["saved_to"], str(output_path))
            self.assertEqual(output_path.read_text(encoding="utf-8"), "print('generated')\n")

    def test_project_json_returns_file_results(self):
        fake_project = SimpleNamespace(
            success=True,
            project_dir="projects/demo",
            files=[SimpleNamespace(filename="main.py", tested_ok=True, test_error="")],
            entry_point="main.py",
            entry_point_ok=True,
            entry_point_error="",
            log="project complete",
        )
        with patch("saleha.cli.commands.ProjectBuilder") as builder_class:
            builder_class.return_value.build.return_value = fake_project
            result = CliRunner().invoke(cli, ["project", "Build a demo", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["files"][0]["filename"], "main.py")
        self.assertTrue(payload["entry_point_ok"])

    def test_doctor_json_returns_check_collection(self):
        with patch("saleha.cli.commands._check_ollama", return_value=(True, "test server")):
            result = CliRunner().invoke(cli, ["doctor", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["healthy"])
        self.assertTrue(any(check["name"].startswith("core/") for check in payload["checks"]))

    def test_project_accepts_custom_output_directory(self):
        fake_project = SimpleNamespace(
            success=True, project_dir="custom/demo", files=[],
            entry_point="", entry_point_ok=None, entry_point_error="", log="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("saleha.cli.commands.ProjectBuilder") as builder_class:
                builder_class.return_value.build.return_value = fake_project
                result = CliRunner().invoke(cli, [
                    "project", "Build a demo", "--output-dir", tmp, "--json"
                ])

            self.assertEqual(result.exit_code, 0, result.output)
            builder_class.assert_called_once_with(model="auto", projects_dir=tmp)

    def test_run_rejects_invalid_attempt_limit(self):
        result = CliRunner().invoke(cli, ["run", "Create a script", "--max-attempts", "0"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("Invalid value for '--max-attempts'", result.output)


if __name__ == "__main__":
    unittest.main()
