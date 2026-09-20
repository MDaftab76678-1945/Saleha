"""Unit tests for tool catalog CLI and self-improvement CLI commands."""
from typing import Any
import json
import unittest
from click.testing import CliRunner
from saleha.cli.commands import cli


class CliSelfBuildingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_cli_tools_json_backward_compatible(self) -> None:
        res = self.runner.invoke(cli, ["tools", "--json"])
        self.assertEqual(res.exit_code, 0)
        data = json.loads(res.output)
        self.assertIn("tools", data)
        names = [t["name"] for t in data["tools"]]
        self.assertIn("web_fetch", names)
        self.assertIn("file_search", names)

    def test_cli_tools_list(self) -> None:
        res = self.runner.invoke(cli, ["tools", "list"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("Registered Saleha Tools", res.output)
        self.assertIn("word_counter", res.output)

    def test_cli_tools_info_found(self) -> None:
        res = self.runner.invoke(cli, ["tools", "info", "word_counter"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("Tool: word_counter", res.output)
        self.assertIn("WordCounterTool", res.output)

    def test_cli_tools_info_not_found(self) -> None:
        res = self.runner.invoke(cli, ["tools", "info", "non_existent_xyz"])
        self.assertNotEqual(res.exit_code, 0)
        self.assertIn("not found in registry", res.output)

    def test_cli_self_improve_status(self) -> None:
        res = self.runner.invoke(cli, ["self-improve", "status"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("Saleha Self-Improvement Engine Status", res.output)
        self.assertIn("Total Core Modules", res.output)
        self.assertIn("Test Coverage", res.output)


if __name__ == "__main__":
    unittest.main()
