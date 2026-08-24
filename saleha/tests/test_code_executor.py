import unittest
import tempfile
from pathlib import Path

from saleha.core.code_executor import CodeExecutor, _check_blocked_imports


class CodeExecutorTests(unittest.TestCase):
    def test_blocked_imports_are_detected(self):
        self.assertIsNotNone(_check_blocked_imports("import socket"))
        self.assertIsNotNone(_check_blocked_imports("from subprocess import run"))
        self.assertIsNone(_check_blocked_imports("import math"))

    def test_safe_code_executes(self):
        result = CodeExecutor(timeout=5, audit=False).execute("print('ok')")

        self.assertTrue(result.success)
        self.assertEqual(result.output.strip(), "ok")
        self.assertEqual(result.exit_code, 0)

    def test_dangerous_import_is_blocked(self):
        result = CodeExecutor(audit=False).execute("import socket\nprint('no')")

        self.assertFalse(result.success)
        self.assertTrue(result.blocked)
        self.assertIn("socket", result.block_reason)

    def test_audit_records_execution_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            executor = CodeExecutor(timeout=5)
            executor.audit_log.path = str(Path(tmp) / "audit.jsonl")

            result = executor.execute("print('ok')")
            records = executor.audit_log.recent()

        self.assertTrue(result.success)
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["allowed"])
        self.assertTrue(records[0]["executed"])
        self.assertTrue(records[0]["success"])
        self.assertEqual(records[0]["exit_code"], 0)

    def test_large_output_is_truncated(self):
        result = CodeExecutor(timeout=5, audit=False).execute("print('x' * 60000)")

        self.assertTrue(result.success)
        self.assertTrue(result.output_truncated)
        self.assertIn("[output truncated]", result.output)

    def test_execution_timeout_returns_controlled_failure(self):
        result = CodeExecutor(timeout=1, audit=False).execute("while True: pass")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, -1)
        self.assertIn("timed out", result.error)


if __name__ == "__main__":
    unittest.main()
