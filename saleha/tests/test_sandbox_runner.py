"""Unit tests for Isolated Container & Process Sandbox Execution Engine."""

import unittest
from saleha.core.sandbox_runner import SandboxRunner, SandboxExecutionResult


class TestSandboxRunner(unittest.TestCase):
    """Test suite for SandboxRunner process containment and safety checks."""

    def setUp(self):
        self.runner = SandboxRunner(default_timeout_sec=5.0)

    def test_run_python_code_success(self):
        res = self.runner.run_python_code("print('SANDBOX_OK')")
        self.assertIsInstance(res, SandboxExecutionResult)
        self.assertTrue(res.success)
        self.assertEqual(res.exit_code, 0)
        self.assertIn("SANDBOX_OK", res.stdout)
        self.assertFalse(res.blocked_by_safety)

    def test_blocks_dangerous_command(self):
        res = self.runner.run_command(["rm", "-rf", "/"])
        self.assertFalse(res.success)
        self.assertTrue(res.blocked_by_safety)
        self.assertIn("Security Alert", res.stderr)


if __name__ == "__main__":
    unittest.main()
