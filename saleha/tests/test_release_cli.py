"""
Unit test for saleha release CLI command.

The command's own docstring/help text no longer make artifact-packaging
or PQC-signing claims (see saleha/cli/release_cli.py: a prior version
hardcoded "696/696 PASSED (100% GREEN)" test results and claimed
"CRYSTALS-Dilithium-5 + Kyber-1024" signing that never happened, fixed in
NOTEBOOK_IMPORT.md pass 47). This test uses --skip-tests so it does not
spawn a real nested pytest run of the whole suite from inside the suite
itself -- an earlier version of this test invoked the command without
that flag, which silently ran the entire saleha/tests/ suite as a
subprocess of itself on every test run, multiplying total suite runtime.
"""

import json
import os
import unittest
from click.testing import CliRunner
from saleha.cli.release_cli import release_cmd


class ReleaseCLITests(unittest.TestCase):

    def test_release_command_execution(self):
        runner = CliRunner()
        result = runner.invoke(release_cmd, ["--channel", "stable", "--skip-tests"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Release Manifest", result.output)
        self.assertIn("Test suite ran", result.output)

        manifest_path = "saleha-release-manifest.json"
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["test_suite"]["ran"], False)
        self.assertNotIn("Kyber", manifest["content_fingerprint_algorithm"])
        self.assertNotIn("Dilithium", manifest["content_fingerprint_algorithm"])
        os.remove(manifest_path)


if __name__ == "__main__":
    unittest.main()

