"""A test pass only real execution can produce (saleha/core/harness/verdict.py)."""

from __future__ import annotations

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from saleha.core.harness.test_runner import TestRunner, TestSuiteResult
from saleha.core.harness.verdict import (
    DID_NOT_RUN,
    FAILED,
    NOTHING_TO_VERIFY,
    NotVerified,
    RunTicket,
    Verified,
    judge_suite_output,
    open_run,
)
from saleha.core.polyglot.polyglot_executor import PolyglotExecutionResult

CODE = "def add(a, b):\n    return a + b\n"
TESTS = (
    "import unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(add(2, 3), 5)\n"
)


def _line(ticket: RunTicket, ran: int, skipped: int = 0, failures: Any = ()) -> str:
    import json
    return ticket.marker + json.dumps({"ran": ran, "skipped": skipped, "failures": list(failures)})


class VerifiedCannotBeConstructedTests(unittest.TestCase):
    def test_direct_construction_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            Verified(object(), ran=3, skipped=0, digest="x")

    def test_not_verified_cannot_claim_a_pass(self) -> None:
        with self.assertRaises(ValueError):
            NotVerified("passed", "trust me")

    def test_suite_result_has_no_settable_pass(self) -> None:
        with self.assertRaises(TypeError):
            TestSuiteResult(passed=True)  # type: ignore[call-arg]
        blank = TestSuiteResult(ran=5)
        self.assertFalse(blank.passed)
        self.assertEqual(blank.status, DID_NOT_RUN)
        with self.assertRaises(AttributeError):
            blank.passed = True  # type: ignore[misc]


class JudgeTests(unittest.TestCase):
    def test_real_result_line_is_a_pass_bound_to_its_code(self) -> None:
        ticket = open_run(CODE, TESTS)
        verdict = judge_suite_output(ticket, "noise\n" + _line(ticket, 2), exit_ok=True)
        self.assertIsInstance(verdict, Verified)
        assert isinstance(verdict, Verified)
        self.assertTrue(verdict.covers(CODE, TESTS))
        self.assertFalse(verdict.covers(CODE + "\n# edited", TESTS))

    def test_ticket_that_was_never_opened_proves_nothing(self) -> None:
        forged = RunTicket("0" * 16, "digest")
        verdict = judge_suite_output(forged, _line(forged, 5), exit_ok=True)
        self.assertEqual(verdict.kind, DID_NOT_RUN)

    def test_ticket_is_judged_once(self) -> None:
        ticket = open_run(CODE, TESTS)
        self.assertIsInstance(judge_suite_output(ticket, _line(ticket, 1), True), Verified)
        self.assertEqual(judge_suite_output(ticket, _line(ticket, 1), True).kind, DID_NOT_RUN)

    def test_line_with_another_runs_nonce_is_ignored(self) -> None:
        mine, other = open_run(CODE, TESTS), open_run(CODE, TESTS)
        verdict = judge_suite_output(mine, _line(other, 4), exit_ok=True)
        self.assertEqual(verdict.kind, DID_NOT_RUN)

    def test_all_skipped_verifies_nothing(self) -> None:
        ticket = open_run(CODE, TESTS)
        verdict = judge_suite_output(ticket, _line(ticket, 3, skipped=3), exit_ok=True)
        self.assertEqual(verdict.kind, NOTHING_TO_VERIFY)

    def test_clean_report_with_nonzero_exit_is_a_failure(self) -> None:
        ticket = open_run(CODE, TESTS)
        verdict = judge_suite_output(ticket, _line(ticket, 2), exit_ok=False)
        self.assertEqual(verdict.kind, FAILED)

    def test_unreadable_payload_did_not_run(self) -> None:
        ticket = open_run(CODE, TESTS)
        verdict = judge_suite_output(ticket, ticket.marker + "{not json", exit_ok=True)
        self.assertEqual(verdict.kind, DID_NOT_RUN)


class RunnerIssuesProofTests(unittest.TestCase):
    def test_real_run_carries_proof_for_exact_code(self) -> None:
        res = TestRunner().run_suite(CODE, test_code=TESTS, timeout=15)
        self.assertTrue(res.passed, res.summary)
        assert res.proof is not None
        self.assertTrue(res.proof.covers(CODE, TESTS))

    def test_chatty_passing_solution_is_judged_on_full_output(self) -> None:
        # The result line is printed last; judging on the 20k-char head of
        # the output used to call this correct solution a crash.
        chatty = CODE + "print('x' * 30000)\n"
        res = TestRunner().run_suite(chatty, test_code=TESTS, timeout=15)
        self.assertTrue(res.passed, res.summary)


class PolyglotTesterTests(unittest.TestCase):
    def test_non_python_run_is_not_reported_as_a_tested_pass(self) -> None:
        from saleha.agents.tester import TesterAgent

        ok = PolyglotExecutionResult(success=True, language="javascript", output="5\n")
        with patch("saleha.core.polyglot.polyglot_executor.PolyglotExecutor.execute", return_value=ok):
            res = TesterAgent().run_suite("console.log(2 + 3);", test_code="// tests",
                                          language="javascript")
        self.assertFalse(res.passed)
        self.assertEqual(res.status, NOTHING_TO_VERIFY)
        self.assertEqual(res.ran, 0)


class OrchestratorRecordsOnlyProvenTests(unittest.TestCase):
    def _orch(self, code: str, tests: str, language: str) -> Any:
        from saleha.agents.coder import CodeResult
        from saleha.agents.planner import PlanResult
        from saleha.agents.reviewer import ReviewResult
        from saleha.agents.tester import TestResult
        from saleha.orchestrator import SalehaOrchestrator

        o = SalehaOrchestrator(model="fake-model", max_healing_attempts=1)
        o.planner.create_plan = MagicMock(return_value=PlanResult(
            success=True, steps=["s"], recommendation="go", raw_response="p", complexity_score=1.0))
        o.coder.generate_code = MagicMock(return_value=CodeResult(
            success=True, code=code, attempts=1, model_used="fake-model", language=language))
        o.coder.generate_tests = MagicMock(return_value=CodeResult(
            success=True, code=tests, attempts=1, model_used="fake-model", language=language))
        o.tester.test_code = MagicMock(return_value=TestResult(passed=True, error_message="", error_type="None"))
        o.reviewer.review_code = MagicMock(return_value=ReviewResult(
            approved=True, feedback="f", model_used="fake-model"))
        return o

    def _run(self, orch: Any, goal: str) -> Any:
        seen: Dict[str, Any] = {}
        with patch("saleha.core.memory.memory_store.memory_store.remember",
                   side_effect=lambda **kw: seen.update(kw) or MagicMock()), \
             patch("saleha.core.memory.memory_store.memory_store.recall", return_value=None), \
             patch("saleha.core.skills.skill_registry.registry.find_skill", return_value=None):
            res = orch.execute_task(goal, use_context=False, generate_tests=True)
        return res, seen

    def test_python_suite_pass_is_recorded_as_tested(self) -> None:
        orch = self._orch(CODE, TESTS, "python")
        res, seen = self._run(orch, "write add in python")
        self.assertTrue(res.success, res.log)
        self.assertTrue(res.tests_passed)
        self.assertEqual(seen.get("source_type"), "verified_execution")

    def test_javascript_suite_that_never_ran_is_not_recorded_as_tested(self) -> None:
        js = "function add(a, b) { return a + b; }\nconsole.log(add(2, 3));\n"
        orch = self._orch(js, "// assert add(2, 3) === 5", "javascript")
        ok = PolyglotExecutionResult(success=True, language="javascript", output="5\n")
        orch.verifier.execute = MagicMock(return_value=MagicMock(
            success=True, blocked=False, output="5\n", error=""))
        with patch("saleha.core.polyglot.polyglot_executor.PolyglotExecutor.execute", return_value=ok):
            res, seen = self._run(orch, "write add in javascript")
        self.assertTrue(res.success, res.log)
        self.assertFalse(res.tests_passed)
        self.assertEqual(seen.get("source_type"), "ran_without_error")
        self.assertIn("Tests not run", res.log)


if __name__ == "__main__":
    unittest.main()
