import unittest
import tempfile
from pathlib import Path

from saleha.core.code_executor import (
    CodeExecutor,
    ExecutionResult,
    _check_blocked_imports,
)


class CodeExecutorTests(unittest.TestCase):
    def test_blocked_imports_are_detected(self) -> None:
        self.assertIsNotNone(_check_blocked_imports("import socket"))
        self.assertIsNotNone(_check_blocked_imports("from subprocess import run"))
        self.assertIsNone(_check_blocked_imports("import math"))

    @staticmethod
    def _why(result: ExecutionResult) -> str:
        """Everything the result knows about itself, for an assert message.

        `assertTrue(result.success)` fails with "False is not true" and stops
        before the later assertions run, so it reports nothing about *why*.
        This test failed exactly once in three full-suite runs (pass 54) and
        that message was all the evidence there was: not the exit code, not
        the error string, not whether the safety layer had blocked it, not
        which backend ran. Four deliberate reproduction attempts -- isolated
        runs, 8-way concurrency, a competing full suite, 60 concurrent
        executions -- never reproduced it, so the next occurrence may be the
        only other chance to diagnose it. It should not be wasted again.
        """
        return (
            f"success={result.success} exit_code={result.exit_code} "
            f"blocked={result.blocked} block_reason={result.block_reason!r} "
            f"backend={getattr(result, 'backend', '?')!r} "
            f"output={result.output[:200]!r} error={(result.error or '')[:300]!r}"
        )

    def test_safe_code_executes(self) -> None:
        result = CodeExecutor(timeout=5, audit=False).execute("print('ok')")

        self.assertTrue(result.success, self._why(result))
        self.assertEqual(result.output.strip(), "ok", self._why(result))
        self.assertEqual(result.exit_code, 0, self._why(result))

    def test_dangerous_import_is_blocked(self) -> None:
        result = CodeExecutor(audit=False).execute("import socket\nprint('no')")

        self.assertFalse(result.success, self._why(result))
        self.assertTrue(result.blocked, self._why(result))
        self.assertIsNotNone(result.block_reason, self._why(result))
        self.assertIn("socket", result.block_reason or "", self._why(result))

    def test_audit_records_execution_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = CodeExecutor(timeout=5)
            audit_log = executor.audit_log
            assert audit_log is not None  # audit=True by default here
            audit_log.path = str(Path(tmp) / "audit.jsonl")

            result = executor.execute("print('ok')")
            records = audit_log.recent()

        self.assertTrue(result.success, self._why(result))
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["allowed"])
        self.assertTrue(records[0]["executed"])
        self.assertTrue(records[0]["success"])
        self.assertEqual(records[0]["exit_code"], 0)

    def test_large_output_is_truncated(self) -> None:
        result = CodeExecutor(timeout=5, audit=False).execute("print('x' * 60000)")

        self.assertTrue(result.success, self._why(result))
        self.assertTrue(result.output_truncated, self._why(result))
        self.assertIn("[output truncated]", result.output)

    def test_execution_timeout_returns_controlled_failure(self) -> None:
        result = CodeExecutor(timeout=1, audit=False).execute("while True: pass")

        self.assertFalse(result.success, self._why(result))
        self.assertEqual(result.exit_code, -1, self._why(result))
        self.assertIn("timed out", result.error or "", self._why(result))


if __name__ == "__main__":
    unittest.main()
