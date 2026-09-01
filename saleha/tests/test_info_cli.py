"""
Unit test for saleha info CLI command.
"""

import unittest
from click.testing import CliRunner
from saleha.cli.info_cli import info_cmd


class InfoCLITests(unittest.TestCase):

    def test_info_command_execution(self):
        runner = CliRunner()
        result = runner.invoke(info_cmd)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("SALEHA AI UNIFIED PLATFORM SPECIFICATIONS", result.output)
        self.assertIn("Platform Version", result.output)
        self.assertIn("Active Model Provider", result.output)


if __name__ == "__main__":
    unittest.main()

