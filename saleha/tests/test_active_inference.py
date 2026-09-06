"""
Tests for the Active Inference gate: ask before guessing.

The defect this guards against, measured on this repo before the gate existed:

    PlannerAgent.create_plan("fix it")
      -> success=True, recommendation=EXECUTE, complexity 0.0
      -> steps: ['"main ise pragati karunga."']

No file, no repo, no bug named -- and the planner reported success and moved
to execution. The two directions matter equally here: the gate must catch
vague goals, and it must NOT nag about specific ones. A gate that asks about
everything is worse than no gate, because it will be turned off.

No model is contacted: the gate is pure text analysis.
"""

from __future__ import annotations

import unittest

from saleha.core.active_inference import (
    Uncertainty,
    active_inference_gate,
    assess_goal,
)


# Goals a person cannot act on without asking something first.
VAGUE = [
    "fix it",
    "make this better",
    "fix that",
    "improve",
    "refactor",
    "do the thing",
    "clean up stuff",
    "add caching",
    "optimize the parser",
    "make the tests faster",
]

# Goals that name what to touch or what "done" means. Must pass untouched.
SPECIFIC = [
    "add a retry decorator to saleha/core/fast_inference.py",
    "rename parse_config to load_config in config.py",
    "write unit tests for the PromptCache eviction path",
    "fix the off-by-one in tot_orchestrator._generate_branch_code",
    "the merge function returns None when both lists are empty, "
    "it should return []",
    "implement binary search over a sorted list of ints",
    "add caching to the inference layer so repeated prompts are not re-run",
    "make the tests in test_fast_inference.py run faster",
]


class VagueGoalsAreCaughtTests(unittest.TestCase):
    def test_every_vague_goal_triggers_a_question(self):
        for goal in VAGUE:
            with self.subTest(goal=goal):
                u = assess_goal(goal)
                self.assertTrue(u.should_ask, f"{goal!r} should have been questioned")
                self.assertTrue(u.question, "a question must be supplied")
                self.assertTrue(u.reasons, "the reason must be explainable")

    def test_empty_goal_is_caught(self):
        for goal in ("", "   ", None):
            u = assess_goal(goal)
            self.assertTrue(u.should_ask)
            self.assertEqual(u.score, 1.0)

    def test_fix_it_scores_at_the_top(self):
        self.assertEqual(assess_goal("fix it").score, 1.0)


class SpecificGoalsPassTests(unittest.TestCase):
    """The more important direction: a gate that nags gets disabled."""

    def test_no_specific_goal_is_blocked(self):
        for goal in SPECIFIC:
            with self.subTest(goal=goal):
                u = assess_goal(goal)
                self.assertFalse(u.should_ask,
                                 f"{goal!r} was needlessly questioned "
                                 f"(score {u.score}, reasons {u.reasons})")

    def test_naming_a_file_is_enough(self):
        self.assertFalse(assess_goal("fix saleha/core/fast_inference.py").should_ask)

    def test_backticked_symbol_counts_as_a_target(self):
        self.assertFalse(assess_goal("fix the bug in `PromptCache.put`").should_ask)

    def test_describing_the_outcome_rescues_a_vague_target(self):
        """Saying what 'correct' looks like is as good as naming a file."""
        vague = "add caching to the inference layer"
        rescued = vague + " so repeated prompts are not re-run"
        self.assertTrue(assess_goal(vague).should_ask)
        self.assertFalse(assess_goal(rescued).should_ask)


class ContextSuppressionTests(unittest.TestCase):
    """A bare 'fix it' is legitimate when the caller already has the file."""

    def test_context_makes_fix_it_actionable(self):
        self.assertTrue(assess_goal("fix it").should_ask)
        self.assertFalse(assess_goal("fix it", context_has_target=True).should_ask)

    def test_context_does_not_rescue_an_empty_goal(self):
        self.assertTrue(assess_goal("", context_has_target=True).should_ask)


class QuestionQualityTests(unittest.TestCase):
    def test_missing_target_asks_for_the_target(self):
        q = assess_goal("fix it").question.lower()
        self.assertTrue("file" in q or "function" in q)

    def test_only_one_question_is_asked(self):
        """Three questions at once is its own kind of unhelpful."""
        for goal in VAGUE:
            with self.subTest(goal=goal):
                self.assertLessEqual(assess_goal(goal).question.count("?"), 2)

    def test_reasons_are_specific_not_generic(self):
        reasons = assess_goal("fix it").reasons
        self.assertTrue(any("it" in r for r in reasons))


class ScoreContractTests(unittest.TestCase):
    def test_score_is_bounded(self):
        for goal in VAGUE + SPECIFIC + ["", "x"]:
            u = assess_goal(goal)
            self.assertGreaterEqual(u.score, 0.0)
            self.assertLessEqual(u.score, 1.0)

    def test_actionable_and_should_ask_are_consistent(self):
        for goal in VAGUE + SPECIFIC:
            u = assess_goal(goal)
            self.assertEqual(u.should_ask, not u.actionable)

    def test_signals_are_reported_for_inspection(self):
        u = assess_goal("fix it")
        for key in ("has_target", "has_action", "bare_referent", "words"):
            self.assertIn(key, u.signals)

    def test_assessment_is_deterministic(self):
        first = assess_goal("optimize the parser").score
        for _ in range(3):
            self.assertEqual(assess_goal("optimize the parser").score, first)

    def test_shared_instance_and_helper_agree(self):
        self.assertEqual(active_inference_gate.assess("fix it").score,
                         assess_goal("fix it").score)

    def test_returns_the_documented_type(self):
        self.assertIsInstance(assess_goal("fix it"), Uncertainty)


class PlannerIntegrationTests(unittest.TestCase):
    """The planner must ask rather than fabricate a plan -- no model needed,
    because the gate short-circuits before any model call."""

    def _planner(self):
        from saleha.agents.planner import PlannerAgent
        return PlannerAgent(model="qwen2.5-coder:3b")

    def test_vague_goal_returns_needs_clarification(self):
        result = self._planner().create_plan("fix it")
        self.assertFalse(result.success)
        self.assertEqual(result.recommendation, "NEEDS_CLARIFICATION")
        self.assertTrue(result.needs_clarification)
        self.assertTrue(result.clarifying_question)
        self.assertTrue(result.uncertainty_reasons)
        self.assertEqual(result.steps, [])

    def test_context_flag_skips_the_gate_in_the_planner(self):
        """With context, create_plan must get past the gate. The model call
        after it is patched out -- what is under test is the gate decision,
        not the model's plan."""
        from unittest.mock import MagicMock, patch
        planner = self._planner()
        reply = MagicMock(success=True, content="Step 1: do the thing",
                          model_used="m", error_message="")
        with patch.object(planner, "think", return_value=reply):
            result = planner.create_plan("fix it", context_has_target=True)
        self.assertNotEqual(result.recommendation, "NEEDS_CLARIFICATION")

    def test_skip_flag_bypasses_the_gate_in_the_planner(self):
        """Batch/non-interactive runs have nobody to answer the question."""
        from unittest.mock import MagicMock, patch
        planner = self._planner()
        reply = MagicMock(success=True, content="Step 1: do the thing",
                          model_used="m", error_message="")
        with patch.object(planner, "think", return_value=reply):
            result = planner.create_plan("fix it", skip_clarity_check=True)
        self.assertNotEqual(result.recommendation, "NEEDS_CLARIFICATION")

    def test_gate_short_circuits_before_any_model_call(self):
        """A vague goal must not cost a round trip."""
        from unittest.mock import patch
        planner = self._planner()
        with patch.object(planner, "think") as think:
            planner.create_plan("fix it")
        think.assert_not_called()

    def test_plan_result_defaults_are_backward_compatible(self):
        from saleha.agents.planner import PlanResult
        r = PlanResult(success=True, steps=["a"], recommendation="EXECUTE")
        self.assertFalse(r.needs_clarification)
        self.assertEqual(r.clarifying_question, "")
        self.assertEqual(r.uncertainty_reasons, [])


if __name__ == "__main__":
    unittest.main()
