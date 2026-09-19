"""
Tests for the multi-agent debate orchestrator.

The behaviour under test is that every position is really model-generated and
that failure is reported as failure. The previous implementation called no
model at all and always returned "ACCEPTED (94.8%)", so these tests are
written to fail loudly if anything drifts back toward a template.

No real model is contacted: the inference engine is injected.
"""

from __future__ import annotations

import unittest
from typing import Any, List
from unittest.mock import MagicMock

from saleha.core.debate_consensus_orchestrator import (
    DebateConsensusOrchestrator,
)
from saleha.core.fast_inference import InferenceResult


def _engine(single: str = "reply", batch_ok: bool = True,
            batch_text: str = "critique") -> Any:
    """Fake FastInference: `run` for solo calls, `run_batch` for the critics."""
    fi = MagicMock()
    fi.run.side_effect = lambda req, **kw: InferenceResult(
        success=True, content=f"{single} [{req.tag}]", tag=req.tag)

    def batch(reqs: List[Any], **kw: Any) -> List[InferenceResult]:
        return [InferenceResult(success=batch_ok,
                                content=f"{batch_text} [{r.tag}]" if batch_ok else "",
                                error="" if batch_ok else "connection refused",
                                tag=r.tag)
                for r in reqs]

    fi.run_batch.side_effect = batch
    return fi


class DebateRunsRealCallsTests(unittest.TestCase):
    def test_every_persona_is_a_model_call(self) -> None:
        fi = _engine()
        v = DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="Postgres vs DynamoDB", num_rounds=1)
        # 1 advocate + 1 arbiter via run(); 3 critics via run_batch().
        self.assertEqual(fi.run.call_count, 2)
        self.assertEqual(fi.run_batch.call_count, 1)
        self.assertEqual(len(fi.run_batch.call_args.args[0]), 3)
        self.assertTrue(v.rounds[0].complete)

    def test_critics_are_not_cached(self) -> None:
        """A warm cache would give all three critics the same answer."""
        fi = _engine()
        DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="t", num_rounds=1)
        self.assertIs(fi.run_batch.call_args.kwargs["use_cache"], False)

    def test_each_critic_gets_a_distinct_instruction(self) -> None:
        fi = _engine()
        DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="t", num_rounds=1)
        prompts = [r.prompt for r in fi.run_batch.call_args.args[0]]
        self.assertEqual(len(set(prompts)), 3)

    def test_topic_reaches_every_persona(self) -> None:
        fi = _engine()
        DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="UNIQUE_TOPIC_XYZ", num_rounds=1)
        for req in fi.run_batch.call_args.args[0]:
            self.assertIn("UNIQUE_TOPIC_XYZ", req.prompt)

    def test_rounds_are_sequential_and_carry_prior_objections(self) -> None:
        fi = _engine()
        DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="t", num_rounds=2)
        second_advocate = fi.run.call_args_list[1].args[0].prompt
        self.assertIn("Previous round:", second_advocate)


class HonestFailureTests(unittest.TestCase):
    """The old code reported 0.948 confidence no matter what happened."""

    def test_total_failure_is_no_decision_not_accepted(self) -> None:
        fi = MagicMock()
        fi.run.side_effect = lambda req, **kw: InferenceResult(
            success=False, error="connection refused", tag=req.tag)
        fi.run_batch.side_effect = lambda reqs, **kw: [
            InferenceResult(success=False, error="connection refused", tag=r.tag)
            for r in reqs]
        v = DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="t", num_rounds=1)
        self.assertEqual(v.elo_confidence_score, 0.0)
        self.assertTrue(v.degraded)
        self.assertIn("NO DECISION", v.adr_markdown)
        self.assertNotIn("ACCEPTED", v.adr_markdown)

    def test_partial_failure_lowers_confidence(self) -> None:
        fi = _engine(batch_ok=False)          # advocate answers, critics do not
        v = DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="t", num_rounds=1)
        self.assertTrue(v.degraded)
        self.assertLess(v.elo_confidence_score, 1.0)
        self.assertGreater(v.elo_confidence_score, 0.0)
        self.assertTrue(v.errors)

    def test_full_participation_is_full_confidence(self) -> None:
        v = DebateConsensusOrchestrator(inference=_engine()).conduct_architectural_debate(
            topic="t", num_rounds=1)
        self.assertEqual(v.elo_confidence_score, 1.0)
        self.assertFalse(v.degraded)

    def test_confidence_is_never_the_old_constant(self) -> None:
        for ok in (True, False):
            v = DebateConsensusOrchestrator(
                inference=_engine(batch_ok=ok)).conduct_architectural_debate(
                topic="t", num_rounds=1)
            self.assertNotEqual(v.elo_confidence_score, 0.948)


class DecisionExtractionTests(unittest.TestCase):
    """An early version returned the document heading as the decision."""

    f = staticmethod(DebateConsensusOrchestrator._first_meaningful_line)

    def test_prefers_prose_under_the_decision_heading(self) -> None:
        adr = ("# Architecture Decision Record: X\n\n## Context\n"
               "We need a store.\n\n## Decision\n"
               "We adopt Postgres because it gives us ACID guarantees.\n")
        self.assertEqual(self.f(adr),
                         "We adopt Postgres because it gives us ACID guarantees.")

    def test_strips_bold_markers(self) -> None:
        self.assertEqual(self.f("## Decision\n\n**Adopt Rust for the hot path only.**\n"),
                         "Adopt Rust for the hot path only.")

    def test_never_returns_a_section_title(self) -> None:
        out = self.f("# Architecture Decision Record\n\n## Context\n\n"
                     "The team must choose a storage engine here.\n")
        self.assertNotEqual(out.lower(), "architecture decision record")
        self.assertIn("storage engine", out)

    def test_empty_input_says_so(self) -> None:
        self.assertEqual(self.f(""), "No decision recorded.")


class BordaConsensusTests(unittest.TestCase):
    def test_borda_aggregation_uniform_weights(self) -> None:
        options = ["Option A", "Option B", "Option C"]
        rankings = [
            ["Option A", "Option B", "Option C"],
            ["Option A", "Option C", "Option B"],
            ["Option B", "Option A", "Option C"],
        ]
        # Option A: 2 + 2 + 1 = 5
        # Option B: 1 + 0 + 2 = 3
        # Option C: 0 + 1 + 0 = 1
        scores = DebateConsensusOrchestrator.aggregate_borda_rankings(options, rankings)
        self.assertEqual(scores["Option A"], 5.0)
        self.assertEqual(scores["Option B"], 3.0)
        self.assertEqual(scores["Option C"], 1.0)

    def test_borda_aggregation_with_voter_weights(self) -> None:
        options = ["Opt1", "Opt2"]
        rankings = [["Opt1", "Opt2"], ["Opt2", "Opt1"]]
        weights = [2.0, 1.0]
        # Opt1: 1*2.0 + 0 = 2.0
        # Opt2: 0 + 1*1.0 = 1.0
        scores = DebateConsensusOrchestrator.aggregate_borda_rankings(options, rankings, weights=weights)
        self.assertEqual(scores["Opt1"], 2.0)
        self.assertEqual(scores["Opt2"], 1.0)

    def test_conduct_debate_includes_borda_scores(self) -> None:
        fi = _engine(batch_text="I prefer Option A then Option B")
        v = DebateConsensusOrchestrator(inference=fi).conduct_architectural_debate(
            topic="Choose architecture",
            options=["Option A", "Option B"],
            num_rounds=1,
        )
        self.assertIn("Option A", v.borda_scores)
        self.assertIn("Option B", v.borda_scores)
        self.assertGreater(v.borda_scores["Option A"], v.borda_scores["Option B"])


if __name__ == "__main__":
    unittest.main()
