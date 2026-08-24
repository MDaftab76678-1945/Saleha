import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from saleha.core.team_orchestrator import TeamOrchestrator, TeamResult
from saleha.cli.commands import cli


class TeamOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.orchestrator = TeamOrchestrator(model="test-model")

    def test_extract_code_helper(self):
        sample_resp = "Here is the implementation:\n```python\ndef add(a, b):\n    return a + b\n```"
        extracted = self.orchestrator._extract_code(sample_resp)
        self.assertEqual(extracted, "def add(a, b):\n    return a + b")

    def test_build_combined_test_runner(self):
        code = "def greet(name): return f'Hello {name}'"
        tests = "class TestGreet(unittest.TestCase): pass"
        combined = self.orchestrator._build_combined_test_runner(code, tests)
        self.assertIn("def greet(name):", combined)
        self.assertIn("class TestGreet", combined)
        self.assertIn("unittest.main", combined)

    def test_deliverable_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.orchestrator._save_deliverables(
                output_dir=tmpdir,
                goal="Build an adder",
                prd="Requirements for adder",
                design="Architecture for adder",
                code="def add(a, b): return a + b",
                security_report="Status: APPROVED",
                test_code="class Test(unittest.TestCase): pass",
                exec_output="OK"
            )

            expected_files = ["PRD.md", "DESIGN.md", "solution.py", "SECURITY.md", "test_solution.py", "DELIVERY_SUMMARY.md"]
            for f in expected_files:
                path = os.path.join(tmpdir, f)
                self.assertTrue(os.path.isfile(path), f"Missing {f}")

    def test_run_team_workflow_mock(self):
        with patch.object(self.orchestrator, "_get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.think.side_effect = [
                MagicMock(success=True, content="1. PRD Content"),
                MagicMock(success=True, content="2. LLD Architecture"),
                MagicMock(success=True, content="```python\ndef solve():\n    return 42\n```"),
                MagicMock(success=True, content="3. Security: APPROVED"),
                MagicMock(success=True, content="```python\nimport unittest\nclass Test(unittest.TestCase):\n    def test_solve(self):\n        self.assertEqual(solve(), 42)\n```"),
            ]
            mock_get_agent.return_value = mock_agent

            with tempfile.TemporaryDirectory() as tmpdir:
                result: TeamResult = self.orchestrator.run_team_workflow(
                    goal="Test Team Goal",
                    output_dir=tmpdir
                )

                self.assertTrue(result.success)
                self.assertEqual(len(result.stages_completed), 5)
                self.assertIn("Product Management", result.stages_completed)
                self.assertIn("Implementation", result.stages_completed)
                self.assertIn("def solve():", result.code)
                self.assertTrue(os.path.isfile(os.path.join(tmpdir, "solution.py")))

    def test_cli_team_json_returns_payload(self):
        fake_team_result = TeamResult(
            success=True,
            goal="Build cache",
            prd="Cache PRD",
            design="Cache Design",
            code="class Cache: pass",
            security_report="APPROVED",
            test_code="class TestCache: pass",
            execution_output="Ran 1 test. OK",
            stages_completed=["Product Management", "Architecture & LLD", "Implementation", "Security Audit", "Test Automation"],
            output_dir="./test_dir",
            attempts=1,
            log="Swarm completed"
        )
        with patch("saleha.cli.commands.TeamOrchestrator") as orchestrator_class:
            orchestrator_class.return_value.run_team_workflow.return_value = fake_team_result
            result = CliRunner().invoke(cli, ["team", "Build cache", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["goal"], "Build cache")
        self.assertEqual(len(payload["stages_completed"]), 5)
        self.assertEqual(payload["code"], "class Cache: pass")


if __name__ == "__main__":
    unittest.main()

