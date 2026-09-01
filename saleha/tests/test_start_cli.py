"""
Unit test for saleha start CLI command.
"""

import unittest
from click.testing import CliRunner
from saleha.cli.start_cli import start_cmd


class StartCLITests(unittest.TestCase):

    def test_start_command_with_choice_info(self):
        runner = CliRunner()
        result = runner.invoke(start_cmd, ["-c", "5"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("SALEHA AI QUICKSTART LAUNCHER", result.output)
        self.assertIn("SALEHA AI UNIFIED PLATFORM SPECIFICATIONS", result.output)

    def test_start_command_with_choice_status(self):
        runner = CliRunner()
        result = runner.invoke(start_cmd, ["-c", "4"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saleha Unified Ecosystem Status", result.output)


if __name__ == "__main__":
    unittest.main()
