import unittest
import os
import tempfile
import json
from click.testing import CliRunner

from saleha.core.sandbox_runner import SandboxRunner, SandboxResult
from saleha.cli.commands import cli


class SandboxRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = SandboxRunner(default_timeout=10)

    def test_safe_code_execution_in_sandbox(self):
        code = "print('Hello from Sandbox!')"
        res: SandboxResult = self.runner.run_in_sandbox(code)
        self.assertTrue(res.success)
        self.assertIn("Hello from Sandbox!", res.output)
        self.assertEqual(res.exit_code, 0)

    def test_runtime_error_captured(self):
        code = "raise ValueError('Custom error inside sandbox')"
        res: SandboxResult = self.runner.run_in_sandbox(code)
        self.assertFalse(res.success)
        self.assertIn("ValueError: Custom error inside sandbox", res.error)
        self.assertNotEqual(res.exit_code, 0)

    def test_dangerous_pattern_blocked(self):
        dangerous_code = "rm -rf /"
        res: SandboxResult = self.runner.run_in_sandbox(dangerous_code)
        self.assertFalse(res.success)
        self.assertTrue(res.blocked)

    def test_cli_sandbox_invocation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("print('Sandbox CLI OK')\n")

            res = CliRunner().invoke(cli, ["sandbox", script_path, "--json"])
            self.assertEqual(res.exit_code, 0)
            payload = json.loads(res.output)
            self.assertTrue(payload["success"])
            self.assertIn("Sandbox CLI OK", payload["output"])


if __name__ == "__main__":
    unittest.main()

