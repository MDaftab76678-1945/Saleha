"""
Saleha v2.0: Ecosystem & Packaging Integration Tests

Validates version synchronization, PyPI package metadata, GitHub Action schema,
VS Code extension manifest, and SWE-bench exporter formats.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
import yaml

import saleha
from saleha.core.swe_bench_exporter import SWEBenchExporter, SWEBenchPrediction
from saleha.core.benchmark_reporter import BenchmarkRun
from saleha.core.swe_leaderboard import TaskResult


class EcosystemIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent.parent

    def test_version_consistency_across_ecosystem(self):
        """Ensures __init__.py, pyproject.toml, and vscode/package.json share exact version."""
        current_ver = saleha.__version__
        self.assertEqual(current_ver, "2.0.0")

        # Check pyproject.toml
        pyproject_path = self.root_dir / "pyproject.toml"
        self.assertTrue(pyproject_path.is_file())
        with open(pyproject_path, "r", encoding="utf-8") as f:
            pyproject_content = f.read()
        self.assertIn('version = "2.0.0"', pyproject_content)

        # Check editors/vscode/package.json
        vscode_pkg = self.root_dir / "editors" / "vscode" / "package.json"
        self.assertTrue(vscode_pkg.is_file())
        with open(vscode_pkg, "r", encoding="utf-8") as f:
            vscode_data = json.load(f)
        self.assertEqual(vscode_data.get("version"), "2.0.0")

    def test_github_action_metadata_schema(self):
        """Validates action.yml exists and has proper composite action schema."""
        action_path = self.root_dir / "action.yml"
        self.assertTrue(action_path.is_file(), "action.yml missing from root")

        with open(action_path, "r", encoding="utf-8") as f:
            action_data = yaml.safe_load(f)

        self.assertIn("name", action_data)
        self.assertIn("description", action_data)
        self.assertIn("inputs", action_data)
        self.assertIn("runs", action_data)
        self.assertEqual(action_data["runs"].get("using"), "composite")
        self.assertTrue(len(action_data["runs"].get("steps", [])) >= 2)

    def test_github_pages_workflow_configured(self):
        """Validates .github/workflows/pages.yml exists."""
        pages_path = self.root_dir / ".github" / "workflows" / "pages.yml"
        self.assertTrue(pages_path.is_file())

        with open(pages_path, "r", encoding="utf-8") as f:
            pages_data = yaml.safe_load(f)

        self.assertIn("jobs", pages_data)
        self.assertIn("deploy", pages_data["jobs"])

    def test_vscode_extension_commands_registered(self):
        """Validates all v2.0 commands are registered in vscode package.json."""
        vscode_pkg = self.root_dir / "editors" / "vscode" / "package.json"
        with open(vscode_pkg, "r", encoding="utf-8") as f:
            data = json.load(f)

        commands = {c["command"] for c in data.get("contributes", {}).get("commands", [])}
        expected_commands = {
            "saleha.fix",
            "saleha.reviewAI",
            "saleha.diffPreview",
            "saleha.memoryProject",
            "saleha.watchAI",
            "saleha.search",
            "saleha.hud",
            "saleha.tune",
        }
        for cmd in expected_commands:
            self.assertIn(cmd, commands, f"Command {cmd} missing in VS Code extension")

    def test_swe_bench_exporter_predictions(self):
        """Validates SWEBenchExporter JSONL serialization and scorecard formatting."""
        exporter = SWEBenchExporter(model_name="saleha-v2.0-test")

        task_results = [
            TaskResult(
                task_id="django__django-11099",
                solved=True,
                time_sec=4.2,
                fix_applied="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            ),
            TaskResult(
                task_id="sympy__sympy-13480",
                solved=False,
                time_sec=6.1,
                fix_applied="def foo(): pass",
                error="AssertionError",
            ),
        ]
        run = BenchmarkRun(
            run_id="test_run_01",
            timestamp="2026-09-01 05:00:00",
            model="saleha-v2.0-test",
            suite="swe_bench",
            total_tasks=2,
            solved=1,
            score_pct=50.0,
            avg_time_sec=5.15,
            metadata={"results": [{"task_id": "django__django-11099", "solved": True}, {"task_id": "sympy__sympy-13480", "solved": False}]},
        )

        out_jsonl = self.root_dir / "scratch" / "test_preds.jsonl"
        saved_path = exporter.export_predictions(run, str(out_jsonl), task_results=task_results)
        self.assertTrue(os.path.isfile(saved_path))

        with open(saved_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["instance_id"], "django__django-11099")
        self.assertIn("--- a/file.py", lines[0]["model_patch"])
        self.assertEqual(lines[0]["model_name_or_path"], "saleha-v2.0-test")

        # Test Scorecard Generation
        scorecard = exporter.generate_leaderboard_scorecard(run)
        self.assertIn("# 🏆 SWE-bench Evaluation Scorecard", scorecard)
        self.assertIn("50.00%", scorecard)
        self.assertIn("django__django-11099", scorecard)
        self.assertIn("sympy__sympy-13480", scorecard)


if __name__ == "__main__":
    unittest.main()
