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
from unittest.mock import MagicMock

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


if __name__ == "__main__":
    unittest.main()
