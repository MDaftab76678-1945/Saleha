"""
Unit test for saleha dogfood CLI command.
"""

import unittest
from click.testing import CliRunner
from saleha.cli.demo_cli import dogfood_cmd


class DemoCLITests(unittest.TestCase):

    def test_dogfood_command_execution(self):
        runner = CliRunner()
        result = runner.invoke(dogfood_cmd)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("SALEHA AI ECOSYSTEM DOGFOODING", result.output)
        self.assertIn("ALL 9 ENGINEERING PILLARS VALIDATED", result.output)


if __name__ == "__main__":
    unittest.main()

