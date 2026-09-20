"""CLI integration tests for `saleha supremacy` command."""

from __future__ import annotations

import json
import unittest
from click.testing import CliRunner

from saleha.cli.commands import cli


class CliSupremacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_cli_supremacy_help(self) -> None:
        res = self.runner.invoke(cli, ["supremacy", "--help"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("Amplify local small models", res.output)
        self.assertIn("Test-Time", res.output)
        self.assertIn("--model", res.output)
        self.assertIn("--trajectories", res.output)
        self.assertIn("--refinements", res.output)
        self.assertIn("--json", res.output)

    def test_cli_supremacy_json_execution(self) -> None:
        res = self.runner.invoke(
            cli,
            [
                "supremacy",
                "Return input as-is",
                "--tests",
                "assert solve(42) == 42\n",
                "--model",
                "mock",
                "--trajectories",
                "2",
                "--json",
            ],
        )
        self.assertEqual(res.exit_code, 0, res.output)
        payload = json.loads(res.output)
        self.assertIn("problem", payload)
        self.assertIn("passed", payload)
        self.assertTrue(payload["passed"])
        self.assertIn("winner_id", payload)
        self.assertIn("winner_code", payload)
        self.assertIn("candidates", payload)
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertIn("amplification_factor", payload)


if __name__ == "__main__":
    unittest.main()
