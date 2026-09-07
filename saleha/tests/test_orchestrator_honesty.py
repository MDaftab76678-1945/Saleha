"""
Cross-orchestrator regression tests for fabricated results.

Each test here corresponds to a real defect found auditing the orchestrator
family. The common shape of all of them: a step that could not run reported
a confident, reassuring result instead of a failure.

  deliberation_engine  a failed security review returned the literal text
                       "No critical security blockers identified." -- an
                       all-clear that no reviewer ever issued.
  team_orchestrator    the two independent critics ran sequentially.
  tot_orchestrator     `_generate_branch_code` accepted `error_msg` and never
                       read it; the three "repair strategies" prepended
                       `if not True: pass`, appended a comment, and called
                       .strip(). None changed behaviour, so the tree search
                       only ever explored cosmetic variants of broken code.

No real model is contacted: the inference engine is injected everywhere.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from saleha.core.fast_inference import InferenceResult


def _engine(ok: bool = True, content: str = "real critique text"):
    fi = MagicMock()
    fi.run_batch.side_effect = lambda reqs, **kw: [
        InferenceResult(success=ok, content=content if ok else "",
                        error="" if ok else "connection refused", tag=r.tag)
        for r in reqs]
    fi.run.side_effect = lambda req, **kw: InferenceResult(
        success=ok, content=content if ok else "",
        error="" if ok else "connection refused", tag=req.tag)
    return fi


class DeliberationCritiqueTests(unittest.TestCase):
    def _engine_obj(self, fi):
        from saleha.core.deliberation_engine import DeliberationEngine
        return DeliberationEngine(inference=fi)

    def test_failed_security_review_is_not_an_all_clear(self):
        sec, perf = self._engine_obj(_engine(ok=False))._run_critique_round(
            "build an auth service", "design")
        for text in (sec, perf):
            self.assertIn("unavailable", text.lower())
            self.assertIn("NOT an all-clear", text)
        # The exact fabricated strings must never come back.
        self.assertNotIn("No critical security blockers identified", sec)
        self.assertNotIn("Performance profile acceptable", perf)

    def test_successful_reviews_are_returned_verbatim(self):
        sec, perf = self._engine_obj(
            _engine(content="found an injection vector"))._run_critique_round(
            "goal", "design")
        self.assertEqual(sec, "found an injection vector")
        self.assertEqual(perf, "found an injection vector")

    def test_both_critics_run_in_one_batch(self):
        fi = _engine()
        self._engine_obj(fi)._run_critique_round("goal", "design")
        self.assertEqual(fi.run_batch.call_count, 1)
        self.assertEqual(len(fi.run_batch.call_args.args[0]), 2)

    def test_critics_get_different_instructions(self):
        fi = _engine()
        self._engine_obj(fi)._run_critique_round("goal", "design")
        prompts = [r.prompt for r in fi.run_batch.call_args.args[0]]
        self.assertEqual(len(set(prompts)), 2)

    def test_design_reaches_both_critics(self):
        fi = _engine()
        self._engine_obj(fi)._run_critique_round("goal", "UNIQUE_DESIGN_XYZ")
        for req in fi.run_batch.call_args.args[0]:
            self.assertIn("UNIQUE_DESIGN_XYZ", req.prompt)


class TeamCritiqueTests(unittest.TestCase):
    def _team(self, fi):
        from saleha.core.team_orchestrator import TeamOrchestrator
        t = TeamOrchestrator()
        t.inference = fi
        return t

    def test_critics_run_concurrently(self):
        fi = _engine()
        self._team(fi)._parallel_critiques("design")
        self.assertEqual(fi.run_batch.call_count, 1)
        self.assertEqual(len(fi.run_batch.call_args.args[0]), 2)

    def test_failed_review_is_marked_not_silently_empty(self):
        sec, sde = self._team(_engine(ok=False))._parallel_critiques("design")
        self.assertIn("NOT an all-clear", sec)
        self.assertIn("NOT an all-clear", sde)

    def test_successful_reviews_pass_through(self):
        sec, sde = self._team(_engine(content="race condition in cache"))\
            ._parallel_critiques("design")
        self.assertEqual(sec, "race condition in cache")
        self.assertEqual(sde, "race condition in cache")


class ToTBranchRepairTests(unittest.TestCase):
    BASE = "def add(a, b):\n    return a - b\n"

    def _tot(self, fi):
        from saleha.core.tot_orchestrator import TreeOfThoughtsOrchestrator
        return TreeOfThoughtsOrchestrator(inference=fi)

    def test_branch_actually_uses_the_error_message(self):
        """`error_msg` was accepted and never read."""
        fi = _engine(content="```python\ndef add(a, b):\n    return a + b\n```")
        self._tot(fi)._generate_branch_code(
            self.BASE, 0, "AssertionError: add(2,3) == 5", goal="add numbers")
        prompt = fi.run.call_args.args[0].prompt
        self.assertIn("AssertionError: add(2,3) == 5", prompt)
        self.assertIn("add numbers", prompt)

    def test_branch_returns_the_repaired_code(self):
        fi = _engine(content="```python\ndef add(a, b):\n    return a + b\n```")
        out = self._tot(fi)._generate_branch_code(self.BASE, 0, "err")
        self.assertIn("a + b", out)
        self.assertNotIn("if not True", out)   # the old cosmetic no-op

    def test_branches_use_distinct_repair_strategies(self):
        fi = _engine(content="```python\nx = 1\n```")
        tot = self._tot(fi)
        prompts = []
        for i in range(3):
            tot._generate_branch_code(self.BASE, i, "err")
            prompts.append(fi.run.call_args.args[0].prompt)
        self.assertEqual(len(set(prompts)), 3)

    def test_unreachable_model_returns_original_unchanged(self):
        """A no-op variant scores like its parent and gets pruned -- honest.
        A cosmetic edit would look like a repair that never happened."""
        out = self._tot(_engine(ok=False))._generate_branch_code(self.BASE, 0, "err")
        self.assertEqual(out, self.BASE)

    def test_empty_reply_falls_back_to_original(self):
        fi = _engine(content="")
        self.assertEqual(
            self._tot(fi)._generate_branch_code(self.BASE, 0, "err"), self.BASE)

    def test_branch_index_wraps_safely(self):
        fi = _engine(content="```python\nx = 1\n```")
        out = self._tot(fi)._generate_branch_code(self.BASE, 7, "err")
        self.assertIn("x = 1", out)

    def test_repairs_are_not_cached(self):
        """A cached repair would give every branch the same patch."""
        fi = _engine(content="```python\nx = 1\n```")
        self._tot(fi)._generate_branch_code(self.BASE, 0, "err")
        self.assertIs(fi.run.call_args.kwargs["use_cache"], False)


class SalehaOrchestratorVerificationTests(unittest.TestCase):
    """
    `SalehaOrchestrator.execute_task` returned success=True for code it had
    never executed.

    The verifier call lives inside `if review_result.approved`. When the
    reviewer never approved and max attempts ran out, the "best-effort accept"
    branch returned success=True having skipped the verifier entirely.
    Measured before the fix: a `1 / 0` body came back as a success with the
    verifier called zero times.
    """

    BROKEN = "def solve():\n    return 1 / 0\n\nsolve()\n"
    WORKING = "def solve():\n    return 1 + 1\n\nsolve()\n"

    def _orch(self, code: str, approved: bool):
        from saleha.agents.coder import CodeResult
        from saleha.agents.planner import PlanResult
        from saleha.agents.reviewer import ReviewResult
        from saleha.agents.tester import TestResult
        from saleha.orchestrator import SalehaOrchestrator

        orch = SalehaOrchestrator(model="fake-model", max_healing_attempts=1)
        orch.planner.create_plan = MagicMock(return_value=PlanResult(
            success=True, steps=["step"], recommendation="go",
            raw_response="plan", complexity_score=1.0))
        orch.coder.generate_code = MagicMock(return_value=CodeResult(
            success=True, code=code, attempts=1, model_used="fake-model"))
        # Syntax/security check passes; the reviewer is the gate under test.
        orch.tester.test_code = MagicMock(return_value=TestResult(
            passed=True, error_message="", error_type="None"))
        orch.reviewer.review_code = MagicMock(return_value=ReviewResult(
            approved=approved, feedback="needs work", model_used="fake-model"))
        return orch

    def _run(self, orch):
        with patch("saleha.core.memory_store.memory_store.recall", return_value=None),              patch("saleha.core.skill_registry.registry.find_skill", return_value=None):
            return orch.execute_task("do a thing", use_context=False)

    def test_unapproved_broken_code_is_not_reported_as_success(self):
        res = self._run(self._orch(self.BROKEN, approved=False))
        self.assertFalse(res.success)

    def test_unapproved_code_is_actually_executed(self):
        orch = self._orch(self.BROKEN, approved=False)
        spy = MagicMock(side_effect=orch.verifier.execute)
        orch.verifier.execute = spy
        self._run(orch)
        self.assertGreaterEqual(
            spy.call_count, 1,
            "unapproved code must be executed before it is accepted")

    def test_unapproved_but_working_code_is_accepted_and_flagged(self):
        """Best-effort accept is fine; it just has to be honest about why."""
        res = self._run(self._orch(self.WORKING, approved=False))
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertIn("reviewer", res.unverified_reason.lower())

    def test_approved_and_working_code_is_verified(self):
        res = self._run(self._orch(self.WORKING, approved=True))
        self.assertTrue(res.success)
        self.assertTrue(res.verified)

    def test_approved_but_broken_code_still_fails(self):
        res = self._run(self._orch(self.BROKEN, approved=True))
        self.assertFalse(res.success)

    def test_memory_replay_is_success_but_not_verified_this_run(self):
        from saleha.orchestrator import SalehaOrchestrator
        cached = MagicMock(code=self.WORKING, model="fake-model", hit_count=3)
        orch = SalehaOrchestrator(model="fake-model")
        with patch("saleha.core.memory_store.memory_store.recall", return_value=cached),              patch("saleha.core.skill_registry.registry.find_skill", return_value=None):
            res = orch.execute_task("do a thing", use_context=False)
        self.assertTrue(res.success)
        self.assertFalse(res.verified)
        self.assertIn("memory", res.unverified_reason.lower())


class SalehaOrchestratorBookkeepingTests(unittest.TestCase):
    """
    Four defects found reading execute_task in full on 2026-09-07, all of them
    bookkeeping that made the run look better or safer than it was.
    """

    GOOD = "def solve():\n    return 1 + 1\n\nsolve()\n"
    BLOCKED = "import os\nos.system('rm -rf /')\n"

    def _orch(self, code, approved=True):
        from saleha.agents.coder import CodeResult
        from saleha.agents.planner import PlanResult
        from saleha.agents.reviewer import ReviewResult
        from saleha.agents.tester import TestResult
        from saleha.orchestrator import SalehaOrchestrator

        o = SalehaOrchestrator(model="fake-model", max_healing_attempts=1)
        o.planner.create_plan = MagicMock(return_value=PlanResult(
            success=True, steps=["s"], recommendation="go",
            raw_response="p", complexity_score=1.0))
        o.coder.generate_code = MagicMock(return_value=CodeResult(
            success=True, code=code, attempts=1, model_used="fake-model"))
        o.tester.test_code = MagicMock(return_value=TestResult(
            passed=True, error_message="", error_type="None"))
        o.reviewer.review_code = MagicMock(return_value=ReviewResult(
            approved=approved, feedback="f", model_used="fake-model"))
        return o

    def test_cache_records_how_the_solution_was_checked(self):
        """
        Without a test suite the only check that ran is "it did not crash",
        which is much weaker than a passing test run. The cache stored both
        identically and the recall path advertised every entry as a
        "previously verified solution".
        """
        seen = {}
        orch = self._orch(self.GOOD)
        with patch("saleha.core.memory_store.memory_store.remember",
                   side_effect=lambda **kw: seen.update(kw) or MagicMock()),              patch("saleha.core.memory_store.memory_store.recall", return_value=None),              patch("saleha.core.skill_registry.registry.find_skill", return_value=None):
            orch.execute_task("goal", use_context=False, generate_tests=False)
        self.assertEqual(seen.get("source_type"), "ran_without_error")

    def test_recall_does_not_claim_verification_that_never_happened(self):
        entry = MagicMock(code=self.GOOD, model="fake-model", hit_count=2,
                          source_type="ran_without_error")
        from saleha.orchestrator import SalehaOrchestrator
        orch = SalehaOrchestrator(model="fake-model")
        with patch("saleha.core.memory_store.memory_store.recall", return_value=entry),              patch("saleha.core.skill_registry.registry.find_skill", return_value=None):
            res = orch.execute_task("goal", use_context=False)
        self.assertTrue(res.success)
        self.assertFalse(res.verified)
        self.assertIn("no test suite", res.unverified_reason)
        self.assertNotIn("previously verified", res.unverified_reason)

    def test_blocked_execution_checkpoints_as_failed(self):
        """
        This exit had no checkpoint, so the session stayed "in_progress" and
        `--resume` would pick a blocked task back up. It also skipped
        metrics_tracker, so blocked runs were invisible and the recorded
        success rate read higher than reality.
        """
        orch = self._orch(self.BLOCKED)
        states = []
        with patch("saleha.core.session_store.session_store.save",
                   side_effect=lambda st: states.append(st.status)),              patch("saleha.core.memory_store.memory_store.recall", return_value=None),              patch("saleha.core.skill_registry.registry.find_skill", return_value=None):
            res = orch.execute_task("goal", use_context=False)
        self.assertFalse(res.success)
        self.assertEqual(states[-1], "failed")

    def test_resume_does_not_rematch_a_different_profile(self):
        """
        On resume the checkpoint's profile is authoritative. Re-deriving it
        could select a different profile than the run being resumed, which
        defeats the point of a checkpoint.
        """
        import inspect
        from saleha.orchestrator import SalehaOrchestrator
        src = inspect.getsource(SalehaOrchestrator.execute_task)
        self.assertIn("elif resumed:", src)
        self.assertIn("active_profile = None", src)


if __name__ == "__main__":
    unittest.main()
