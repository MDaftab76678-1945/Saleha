"""CLI integration tests for `saleha octopus` command."""

from __future__ import annotations

import json
import unittest
from click.testing import CliRunner

from saleha.cli.commands import cli


class CliOctopusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_cli_octopus_help(self) -> None:
        res = self.runner.invoke(cli, ["octopus", "--help"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("Octopus Multi-Agent Coordination Engine", res.output)
        self.assertIn("--model", res.output)
        self.assertIn("--workers", res.output)
        self.assertIn("--json", res.output)

    def test_cli_octopus_json_execution(self) -> None:
        res = self.runner.invoke(
            cli,
            ["octopus", "Build a minimal logging utility", "--model", "mock", "--json"],
        )
        self.assertEqual(res.exit_code, 0, res.output)
        payload = json.loads(res.output)
        self.assertIn("execution_id", payload)
        self.assertIn("goal", payload)
        self.assertIn("brain_outputs", payload)
        self.assertEqual(len(payload["brain_outputs"]), 8)
        self.assertIn("planner", payload["brain_outputs"])
        self.assertIn("architect", payload["brain_outputs"])
        self.assertIn("coder", payload["brain_outputs"])
        self.assertIn("security", payload["brain_outputs"])
        self.assertIn("qa", payload["brain_outputs"])
        self.assertIn("sre", payload["brain_outputs"])
        self.assertIn("critic", payload["brain_outputs"])
        self.assertIn("toolforge", payload["brain_outputs"])


if __name__ == "__main__":
    unittest.main()
