"""Unit tests for Hardened Isolated Sandbox Engine."""

from __future__ import annotations

import unittest
from saleha.core.hardened_sandbox import HardenedSandboxEngine, HardenedExecutionResult


class HardenedSandboxTests(unittest.TestCase):

    def setUp(self):
        # Force process-level sandbox for fast local test deterministic execution
        self.sandbox = HardenedSandboxEngine(prefer_docker=False)

    def test_execute_simple_python_code_success(self):
        code = "print('Hello from hardened sandbox!')\nx = 10 * 5\nprint(f'Result: {x}')"
        res = self.sandbox.execute_code(code, timeout=5)

        self.assertTrue(res.success)
        self.assertIn("Hello from hardened sandbox!", res.output)
        self.assertIn("Result: 50", res.output)
        self.assertEqual(res.sandbox_tier, "process")
        self.assertIsNotNone(res.resource_usage)
        self.assertEqual(res.resource_usage.exit_code, 0)
        self.assertFalse(res.resource_usage.timed_out)

    def test_execute_failing_code_captures_error(self):
        code = "raise ValueError('Intentional sandbox exception')"
        res = self.sandbox.execute_code(code, timeout=5)

        self.assertFalse(res.success)
        self.assertIn("ValueError: Intentional sandbox exception", res.error)
        self.assertNotEqual(res.resource_usage.exit_code, 0)

    def test_execute_infinite_loop_times_out(self):
        code = "import time\nwhile True:\n    time.sleep(0.1)"
        res = self.sandbox.execute_code(code, timeout=1)

        self.assertFalse(res.success)
        self.assertTrue(res.resource_usage.timed_out)
        self.assertIn("timed out", res.error.lower())


if __name__ == "__main__":
    unittest.main()
