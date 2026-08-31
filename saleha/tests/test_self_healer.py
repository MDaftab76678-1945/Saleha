"""Unit tests for Autonomous Self-Healing Engine."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch, MagicMock
from saleha.core.self_healer import SelfHealingEngine, StackFrame, ErrorDiagnostics, HealResult


class SelfHealingEngineTests(unittest.TestCase):

    def setUp(self):
        self.healer = SelfHealingEngine(root_dir=".")

    def test_parse_python_traceback_error(self):
        raw_tb = """
Traceback (most recent call last):
  File "saleha/core/smart_router.py", line 356, in SmartRouter
    def classify_task_tier(self, task: str) -> Dict[str, Any]:
NameError: name 'Any' is not defined
"""
        diags = self.healer.parse_error_output(raw_tb)
        self.assertEqual(diags.error_type, "NameError")
        self.assertIn("name 'Any' is not defined", diags.message)
        self.assertEqual(len(diags.frames), 1)
        self.assertIn("smart_router.py", diags.faulting_file)
        self.assertEqual(diags.faulting_line, 356)

    def test_parse_pytest_failure_output(self):
        raw_pytest = """
=========================== short test summary info ===========================
FAILED saleha/tests/test_agentic_loop.py::AgentLoopTests::test_on_event_streaming - NameError: name 'time' is not defined
"""
        diags = self.healer.parse_error_output(raw_pytest)
        self.assertEqual(diags.error_type, "NameError")
        self.assertIn("name 'time' is not defined", diags.message)

    def test_parse_compiler_linter_output(self):
        raw_err = "saleha/core/codebase_indexer.py:264:10: SyntaxError: invalid syntax"
        diags = self.healer.parse_error_output(raw_err)
        self.assertIn("codebase_indexer.py", diags.faulting_file)
        self.assertEqual(diags.faulting_line, 264)

    def test_run_command_success_and_failure(self):
        # 1. Success command
        code_ok, out_ok = self.healer.run_command('python -c "print(123)"')
        self.assertEqual(code_ok, 0)
        self.assertIn("123", out_ok)

        # 2. Failing command
        code_fail, out_fail = self.healer.run_command('python -c "raise ValueError(\'test_fail\')"')
        self.assertNotEqual(code_fail, 0)
        self.assertIn("ValueError", out_fail)

    def test_auto_heal_already_passing_command(self):
        res = self.healer.auto_heal('python -c "print(42)"')
        self.assertTrue(res.success)
        self.assertEqual(res.attempts_made, 0)
        self.assertTrue(res.verified)


if __name__ == "__main__":
    unittest.main()
