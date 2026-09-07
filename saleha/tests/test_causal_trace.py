"""
Tests for causal context tracing.

What this replaces: `CausalMemoryTracer` from the notebook, which answers the
right question -- which retrieved memory actually caused the answer? -- using
forward hooks on `model.transformer.h[...]` and KL divergence over output
distributions. Ollama's HTTP API exposes no activations, logits or weights, so
that approach is unusable here. Input-level leave-one-out ablation answers the
same causal question with the access this architecture actually has.

Verified against a real model (qwen2.5-coder:3b), goal "write a function that
adds two numbers", three context pieces:

    0.7255  memory:api_rule        (a naming convention the answer must follow)
    0.0000  memory:irrelevant      (the office coffee machine)
    0.0000  repo:unrelated_code    (an unrelated class)

with a measured noise floor of 0.0000. That run is recorded here, not
asserted -- a test that needs a model installed is a flake.
"""

from __future__ import annotations

import unittest

from saleha.core.causal_trace import (
    CausalTracer,
    ContextPiece,
    answer_distance,
)
from saleha.core.fast_inference import InferenceResult


class _Engine:
    """
    Deterministic stand-in. The answer depends only on whether the piece
    named in `decisive` is still present, so influence is known in advance.
    """

    # The prompt carries piece TEXT, not piece ids, so the marker must be a
    # phrase from the decisive piece's text. Matching on the id silently made
    # every ablation identical and every influence 0.0 -- the tests caught it.
    def __init__(self, decisive="verb_something", noisy=False):
        self.decisive = decisive
        self.noisy = noisy
        self._noise_counter = 0

    def _answer(self, prompt):
        if self.decisive and self.decisive not in prompt:
            return "def add(a, b): return a + b"
        return "def verb_add(a, b): return a + b  # follows the naming rule"

    def run(self, request, **kwargs):
        return InferenceResult(success=True, tag=request.tag,
                               content=self._answer(request.prompt))

    def run_batch(self, requests, **kwargs):
        out = []
        for request in requests:
            text = self._answer(request.prompt)
            if self.noisy and request.tag.startswith("noise"):
                self._noise_counter += 1
                text = f"{text} # variant {self._noise_counter}"
            out.append(InferenceResult(success=True, tag=request.tag,
                                       content=text))
        return out


def _pieces():
    return [
        ContextPiece("api_rule", "Functions must be named verb_something.",
                     "memory"),
        ContextPiece("irrelevant", "The coffee machine is on floor three.",
                     "memory"),
        ContextPiece("unrelated_code", "class Widget: pass", "repo"),
    ]


class AnswerDistanceTests(unittest.TestCase):
    def test_identical_answers_are_zero(self):
        self.assertEqual(answer_distance("same text", "same text"), 0.0)

    def test_completely_different_answers_are_high(self):
        self.assertGreater(answer_distance("alpha beta", "zulu yankee"), 0.5)

    def test_one_empty_side_is_total_change(self):
        self.assertEqual(answer_distance("something", ""), 1.0)
        self.assertEqual(answer_distance("", "something"), 1.0)

    def test_both_empty_is_no_change(self):
        self.assertEqual(answer_distance("", ""), 0.0)

    def test_case_and_punctuation_do_not_count_as_causation(self):
        self.assertEqual(answer_distance("Hello, World!", "hello world"), 0.0)

    def test_distance_is_bounded(self):
        for a, b in (("x", "y"), ("", "z"), ("long " * 50, "short")):
            value = answer_distance(a, b)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class PromptConstructionTests(unittest.TestCase):
    def test_all_pieces_are_included(self):
        prompt = CausalTracer.build_prompt("goal", _pieces())
        for piece in _pieces():
            self.assertIn(piece.text, prompt)

    def test_skip_removes_exactly_one_piece(self):
        prompt = CausalTracer.build_prompt("goal", _pieces(), skip="api_rule")
        self.assertNotIn("verb_something", prompt)
        self.assertIn("coffee machine", prompt)
        self.assertIn("Widget", prompt)

    def test_the_goal_always_survives(self):
        prompt = CausalTracer.build_prompt("THE_GOAL", _pieces(),
                                           skip="api_rule")
        self.assertIn("THE_GOAL", prompt)

    def test_no_pieces_still_yields_a_prompt(self):
        self.assertIn("THE_GOAL", CausalTracer.build_prompt("THE_GOAL", []))


class TraceTests(unittest.TestCase):
    def test_the_decisive_piece_gets_the_influence(self):
        trace = CausalTracer(inference=_Engine()).trace("add two numbers",
                                                        _pieces())
        ranked = trace.ranked
        self.assertEqual(ranked[0].piece_id, "api_rule")
        self.assertGreater(ranked[0].influence, 0.0)

    def test_irrelevant_pieces_measure_as_zero(self):
        trace = CausalTracer(inference=_Engine()).trace("goal", _pieces())
        by_id = {i.piece_id: i.influence for i in trace.influences}
        self.assertEqual(by_id["irrelevant"], 0.0)
        self.assertEqual(by_id["unrelated_code"], 0.0)

    def test_dead_weight_is_identified(self):
        trace = CausalTracer(inference=_Engine()).trace("goal", _pieces())
        dead = {i.piece_id for i in trace.dead_weight()}
        self.assertEqual(dead, {"irrelevant", "unrelated_code"})

    def test_above_noise_keeps_only_the_real_effect(self):
        trace = CausalTracer(inference=_Engine()).trace("goal", _pieces())
        self.assertEqual([i.piece_id for i in trace.above_noise()],
                         ["api_rule"])

    def test_every_piece_is_measured(self):
        trace = CausalTracer(inference=_Engine()).trace("goal", _pieces())
        self.assertEqual(len(trace.influences), 3)
        self.assertTrue(all(i.measured for i in trace.influences))

    def test_call_count_is_reported(self):
        """N pieces + baseline + noise samples. The cost is real and visible."""
        trace = CausalTracer(inference=_Engine()).trace(
            "goal", _pieces(), noise_samples=2)
        self.assertEqual(trace.calls_made, 1 + 2 + 3)

    def test_no_pieces_is_handled(self):
        trace = CausalTracer(inference=_Engine()).trace("goal", [])
        self.assertEqual(trace.influences, [])
        self.assertIn("no context pieces", trace.describe())

    def test_describe_marks_pieces_above_the_noise_floor(self):
        trace = CausalTracer(inference=_Engine()).trace("goal", _pieces())
        self.assertIn("api_rule", trace.describe())
        self.assertIn("noise floor", trace.describe())


class NoiseFloorTests(unittest.TestCase):
    """Without this, an influence of 0.03 could just be the model wobbling."""

    def test_a_deterministic_model_has_a_zero_floor(self):
        floor = CausalTracer(inference=_Engine()).measure_noise_floor(
            "goal", _pieces(), samples=3)
        self.assertEqual(floor, 0.0)

    def test_a_wobbling_model_raises_the_floor(self):
        floor = CausalTracer(inference=_Engine(noisy=True)).measure_noise_floor(
            "goal", _pieces(), samples=3)
        self.assertGreater(floor, 0.0)

    def test_one_sample_cannot_measure_variance(self):
        self.assertEqual(
            CausalTracer(inference=_Engine()).measure_noise_floor(
                "goal", _pieces(), samples=1), 0.0)

    def test_calls_are_pinned_to_temperature_zero(self):
        """Sampling noise is not a causal effect."""
        tracer = CausalTracer(inference=_Engine())
        request = tracer._request("prompt", "tag")
        self.assertEqual(request.options["temperature"], 0.0)
        self.assertIn("seed", request.options)


class FailureHandlingTests(unittest.TestCase):
    def test_a_failed_baseline_reports_rather_than_inventing_influence(self):
        class DeadBaseline:
            def run(self, request, **kwargs):
                return InferenceResult(success=False, error="model down",
                                       tag=request.tag)

            def run_batch(self, requests, **kwargs):
                return []

        trace = CausalTracer(inference=DeadBaseline()).trace("goal", _pieces())
        self.assertEqual(trace.baseline_answer, "")
        self.assertTrue(all(not i.measured for i in trace.influences))
        self.assertEqual(trace.ranked, [])

    def test_one_failed_ablation_does_not_poison_the_others(self):
        class PartlyDead(_Engine):
            def run_batch(self, requests, **kwargs):
                out = []
                for request in requests:
                    if request.tag == "irrelevant":
                        out.append(InferenceResult(success=False,
                                                   error="timeout",
                                                   tag=request.tag))
                    else:
                        out.append(InferenceResult(
                            success=True, tag=request.tag,
                            content=self._answer(request.prompt)))
                return out

        trace = CausalTracer(inference=PartlyDead()).trace(
            "goal", _pieces(), noise_samples=0)
        by_id = {i.piece_id: i for i in trace.influences}
        self.assertFalse(by_id["irrelevant"].measured)
        self.assertTrue(by_id["api_rule"].measured)
        self.assertEqual(trace.ranked[0].piece_id, "api_rule")


class PairAblationTests(unittest.TestCase):
    """Leave-one-out misses pieces that only matter together."""

    def test_every_pair_is_measured(self):
        tracer = CausalTracer(inference=_Engine())
        pairs = tracer.ablate_pairs("goal", _pieces(), "baseline answer")
        self.assertEqual(len(pairs), 3)      # 3 choose 2

    def test_a_single_piece_has_no_pairs(self):
        tracer = CausalTracer(inference=_Engine())
        self.assertEqual(tracer.ablate_pairs("goal", _pieces()[:1], "x"), {})


if __name__ == "__main__":
    unittest.main()
