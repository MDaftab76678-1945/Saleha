"""
Tests for evidence-based task completion (saleha/core/task_evidence.py).

These cover the real bug this system exists to prevent: an agent declaring
a task finished without having actually done or verified the work --
observed for real against SWE-bench Lite instances, where a model called
finish() on turn 1 with a fabricated summary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from saleha.core.task_evidence import (
    BudgetExceeded,
    Evidence,
    EvidenceKind,
    EvidenceLedger,
    ResourceBudget,
    TaskState,
    verify_file_exists,
    verify_python_syntax,
    verify_tests_pass,
)


class TaskStateMachineTests(unittest.TestCase):
    def test_starts_in_created(self):
        led = EvidenceLedger(goal="x")
        self.assertEqual(led.state, TaskState.CREATED)
        self.assertFalse(led.is_terminal)

    def test_cannot_jump_created_straight_to_accepted(self):
        """The exact fabricated-completion jump must be impossible."""
        led = EvidenceLedger(goal="x")
        with self.assertRaises(ValueError) as ctx:
            led.transition(TaskState.ACCEPTED)
        self.assertIn("illegal transition", str(ctx.exception))

    def test_legal_path_to_accepted(self):
        led = EvidenceLedger(goal="x")
        led.transition(TaskState.ANALYZING)
        led.transition(TaskState.IMPLEMENTING)
        led.transition(TaskState.VERIFYING)
        led.transition(TaskState.ACCEPTED)
        self.assertEqual(led.state, TaskState.ACCEPTED)
        self.assertTrue(led.is_terminal)

    def test_terminal_states_cannot_transition_out(self):
        led = EvidenceLedger(goal="x")
        led.fail("nope")
        self.assertEqual(led.state, TaskState.FAILED)
        with self.assertRaises(ValueError):
            led.transition(TaskState.IMPLEMENTING)

    def test_history_records_every_transition(self):
        led = EvidenceLedger(goal="x")
        led.transition(TaskState.ANALYZING, "started")
        led.transition(TaskState.VERIFYING, "checking")
        states = [h["state"] for h in led.history]
        self.assertEqual(states, ["CREATED", "ANALYZING", "VERIFYING"])
        self.assertEqual(led.history[1]["note"], "started")


class EvidenceGateTests(unittest.TestCase):
    def test_no_evidence_means_not_admissible(self):
        led = EvidenceLedger(goal="fix bug", required={EvidenceKind.FILE_READ})
        verdict = led.judge_completion()
        self.assertFalse(verdict.admissible)
        self.assertFalse(bool(verdict))
        self.assertIn("file_read", verdict.reason)
        self.assertIn("summary is not evidence", verdict.reason)

    def test_evidence_makes_it_admissible(self):
        led = EvidenceLedger(goal="fix bug", required={EvidenceKind.FILE_READ})
        led.record(EvidenceKind.FILE_READ, "app.py", "test")
        verdict = led.judge_completion()
        self.assertTrue(verdict.admissible)
        self.assertEqual(verdict.missing, [])

    def test_partial_evidence_still_rejected(self):
        led = EvidenceLedger(
            goal="fix bug",
            required={EvidenceKind.FILE_READ, EvidenceKind.TESTS_PASSED},
        )
        led.record(EvidenceKind.FILE_READ, "app.py", "test")
        verdict = led.judge_completion()
        self.assertFalse(verdict.admissible)
        self.assertEqual(verdict.missing, [EvidenceKind.TESTS_PASSED])
        self.assertEqual(verdict.satisfied, [EvidenceKind.FILE_READ])

    def test_accept_refuses_without_evidence_and_keeps_state(self):
        led = EvidenceLedger(goal="x", required={EvidenceKind.TESTS_PASSED})
        led.transition(TaskState.ANALYZING)
        verdict = led.accept()
        self.assertFalse(verdict.admissible)
        self.assertEqual(led.state, TaskState.ANALYZING)  # did NOT accept

    def test_accept_routes_through_verifying(self):
        """Acceptance must always show verification happened first."""
        led = EvidenceLedger(goal="x", required={EvidenceKind.FILE_READ})
        led.transition(TaskState.ANALYZING)
        led.record(EvidenceKind.FILE_READ, "a.py", "test")
        verdict = led.accept()
        self.assertTrue(verdict.admissible)
        self.assertEqual(led.state, TaskState.ACCEPTED)
        states = [h["state"] for h in led.history]
        self.assertIn("VERIFYING", states)
        self.assertLess(states.index("VERIFYING"), states.index("ACCEPTED"))

    def test_evidence_carries_its_source(self):
        led = EvidenceLedger(goal="x")
        ev = led.record(EvidenceKind.FILE_READ, "a.py", "my_source")
        self.assertIsInstance(ev, Evidence)
        self.assertEqual(ev.source, "my_source")
        self.assertIn("my_source", str(ev))


class ResourceBudgetTests(unittest.TestCase):
    def test_unlimited_by_default(self):
        b = ResourceBudget()
        for _ in range(100):
            b.spend(tool_calls=1)
        self.assertEqual(b.tool_calls_used, 100)

    def test_tool_call_limit_raises(self):
        b = ResourceBudget(max_tool_calls=3)
        b.spend(tool_calls=1)
        b.spend(tool_calls=1)
        b.spend(tool_calls=1)
        with self.assertRaises(BudgetExceeded) as ctx:
            b.spend(tool_calls=1)
        self.assertIn("tool call budget", str(ctx.exception))

    def test_cost_limit_raises(self):
        b = ResourceBudget(max_cost_usd=0.10)
        b.spend(cost_usd=0.05)
        with self.assertRaises(BudgetExceeded) as ctx:
            b.spend(cost_usd=0.06)
        self.assertIn("cost budget", str(ctx.exception))

    def test_time_limit_raises(self):
        b = ResourceBudget(max_seconds=0.05)
        time.sleep(0.08)
        with self.assertRaises(BudgetExceeded) as ctx:
            b.check()
        self.assertIn("time budget", str(ctx.exception))

    def test_remaining_tool_calls(self):
        b = ResourceBudget(max_tool_calls=5)
        b.spend(tool_calls=2)
        self.assertEqual(b.remaining_tool_calls(), 3)
        self.assertIsNone(ResourceBudget().remaining_tool_calls())


class RealVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.led = EvidenceLedger(goal="x")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_file_exists_only_records_when_real(self):
        missing = os.path.join(self.tmp, "nope.py")
        self.assertFalse(verify_file_exists(missing, self.led))
        self.assertFalse(self.led.has(EvidenceKind.FILE_EXISTS))

        real = os.path.join(self.tmp, "yes.py")
        with open(real, "w") as f:
            f.write("x = 1\n")
        self.assertTrue(verify_file_exists(real, self.led))
        self.assertTrue(self.led.has(EvidenceKind.FILE_EXISTS))

    def test_syntax_check_rejects_broken_python(self):
        bad = os.path.join(self.tmp, "bad.py")
        with open(bad, "w") as f:
            f.write("def broken(:\n")
        self.assertFalse(verify_python_syntax(bad, self.led))
        self.assertFalse(self.led.has(EvidenceKind.SYNTAX_VALID))

    def test_syntax_check_accepts_valid_python(self):
        good = os.path.join(self.tmp, "good.py")
        with open(good, "w") as f:
            f.write("def ok():\n    return 1\n")
        self.assertTrue(verify_python_syntax(good, self.led))
        self.assertTrue(self.led.has(EvidenceKind.SYNTAX_VALID))

    def test_tests_pass_records_only_on_exit_zero(self):
        ok = verify_tests_pass([sys.executable, "-c", "import sys; sys.exit(0)"],
                               cwd=self.tmp, ledger=self.led)
        self.assertTrue(ok)
        self.assertTrue(self.led.has(EvidenceKind.TESTS_PASSED))

    def test_failing_tests_record_nothing(self):
        ok = verify_tests_pass([sys.executable, "-c", "import sys; sys.exit(1)"],
                               cwd=self.tmp, ledger=self.led)
        self.assertFalse(ok)
        self.assertFalse(self.led.has(EvidenceKind.TESTS_PASSED))

    def test_missing_command_degrades_to_no_evidence(self):
        """A missing runner must be 'no evidence', not a crash."""
        ok = verify_tests_pass(["definitely-not-a-real-binary-xyz"],
                               cwd=self.tmp, ledger=self.led)
        self.assertFalse(ok)
        self.assertFalse(self.led.has(EvidenceKind.TESTS_PASSED))


class SummaryTests(unittest.TestCase):
    def test_summary_is_complete_and_honest(self):
        led = EvidenceLedger(goal="fix the parser",
                             required={EvidenceKind.FILE_READ,
                                       EvidenceKind.TESTS_PASSED})
        led.record(EvidenceKind.FILE_READ, "parser.py", "test")
        s = led.summary()
        self.assertEqual(s["goal"], "fix the parser")
        self.assertEqual(s["state"], "CREATED")
        self.assertEqual(s["evidence_count"], 1)
        self.assertFalse(s["admissible"])
        self.assertIn("tests_passed", s["reason"])
        self.assertIn("file_read", s["kinds_present"])
        self.assertIn("budget", s)


if __name__ == "__main__":
    unittest.main()
