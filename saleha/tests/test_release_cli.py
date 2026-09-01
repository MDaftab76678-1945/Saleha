"""
Unit test for saleha release CLI command.
"""

import unittest
from click.testing import CliRunner
from saleha.cli.release_cli import release_cmd


class ReleaseCLITests(unittest.TestCase):

    def test_release_command_execution(self):
        runner = CliRunner()
        result = runner.invoke(release_cmd, ["--channel", "stable"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PRODUCTION RELEASE PIPELINE", result.output)
        self.assertIn("Official Production Release Artifacts", result.output)
        self.assertIn("successfully validated", result.output)


if __name__ == "__main__":
    unittest.main()

