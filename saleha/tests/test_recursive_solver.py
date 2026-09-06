"""Unit tests for the Recursive Intelligence Network Problem Solver."""

import unittest
from saleha.core.recursive_solver import RecursiveSolver, ReasoningPath, RecursiveSolveResult


class TestRecursiveSolver(unittest.TestCase):
    """Test suite for RecursiveSolver 7-node intelligence network."""

    def setUp(self):
        self.solver = RecursiveSolver(model="mock")

    def test_interpret_problem_generates_spec(self):
        spec = self.solver._interpret_problem("Sort an array of integers in O(n log n)")
        self.assertIsInstance(spec, str)
        self.assertTrue(len(spec) > 0)

    def test_activate_knowledge_returns_principles(self):
        principles = self.solver._activate_knowledge("Sort array", "Problem Spec")
        self.assertIsInstance(principles, list)
        self.assertTrue(len(principles) > 0)

    def test_generate_reasoning_paths_returns_three_distinct_trajectories(self):
        paths = self.solver._generate_reasoning_paths("Binary Search Tree lookup", "Spec")
        self.assertEqual(len(paths), 3)
        path_ids = {p.path_id for p in paths}
        self.assertEqual(path_ids, {"path_a", "path_b", "path_c"})

    def test_cross_evaluate_paths_selects_best_score(self):
        paths = [
            ReasoningPath(path_id="a", name="Path A", strategy="A", score=7.0),
            ReasoningPath(path_id="b", name="Path B", strategy="B", score=9.5),
            ReasoningPath(path_id="c", name="Path C", strategy="C", score=8.0),
        ]
        winner_id, winner = self.solver._cross_evaluate_paths(paths)
        self.assertEqual(winner_id, "b")
        self.assertEqual(winner.score, 9.5)

    def test_solve_end_to_end(self):
        result = self.solver.solve("Calculate factorial of n")
        self.assertIsInstance(result, RecursiveSolveResult)
        self.assertTrue(len(result.paths_explored) >= 3)
        self.assertTrue(len(result.final_code) > 0)
        self.assertIn("Recursive", result.log)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Regression: node 3 used to return three hardcoded ReasoningPath objects with
# literal scores (8.5 / 9.0 / 8.0). Since node 5 picks max(score), `path_b`
# won for EVERY goal ever submitted -- the "multi-path exploration" never
# read the problem. Measured before the fix: three unrelated goals produced
# byte-identical paths and the same winner.
# ---------------------------------------------------------------------------

import json as _json
from unittest.mock import MagicMock

from saleha.core.recursive_solver import ReasoningPath
from saleha.core.fast_inference import InferenceResult


def _engine(payloads):
    """payloads: list of dicts (or None for a failed call), one per path."""
    fi = MagicMock()

    def batch(reqs, **kw):
        out = []
        for pl, r in zip(payloads, reqs):
            out.append(InferenceResult(
                success=pl is not None,
                content=_json.dumps(pl) if pl is not None else "",
                error="" if pl is not None else "connection refused",
                tag=r.tag))
        return out

    fi.run_batch.side_effect = batch
    return fi


def _payload(suitability, strategy="s"):
    return {"strategy": strategy, "time_complexity": "O(n)",
            "space_complexity": "O(1)", "pros": ["p"], "cons": ["c"],
            "suitability": suitability}


def test_paths_reflect_model_scores_not_hardcoded_constants():
    fi = _engine([_payload(3.0), _payload(9.5), _payload(4.0)])
    solver = RecursiveSolver(inference=fi)
    paths = solver._generate_reasoning_paths("goal", "spec")
    assert [p.score for p in paths] == [3.0, 9.5, 4.0]
    # None of the old hardcoded values survive.
    assert {p.score for p in paths} != {8.5, 9.0, 8.0}


def test_winner_follows_the_goal_specific_score():
    """The old code always returned path_b; now any path can win."""
    solver = RecursiveSolver(inference=_engine(
        [_payload(9.0), _payload(2.0), _payload(3.0)]))
    win, best = solver._cross_evaluate_paths(
        solver._generate_reasoning_paths("reverse a linked list", ""))
    assert win == "path_a"

    solver2 = RecursiveSolver(inference=_engine(
        [_payload(1.0), _payload(2.0), _payload(9.0)]))
    win2, _ = solver2._cross_evaluate_paths(
        solver2._generate_reasoning_paths("stream a huge file", ""))
    assert win2 == "path_c"


def test_each_path_asks_about_a_different_approach():
    fi = _engine([_payload(5.0)] * 3)
    RecursiveSolver(inference=fi)._generate_reasoning_paths("g", "")
    prompts = [r.prompt for r in fi.run_batch.call_args.args[0]]
    assert len(set(prompts)) == 3


def test_goal_reaches_every_path_prompt():
    fi = _engine([_payload(5.0)] * 3)
    RecursiveSolver(inference=fi)._generate_reasoning_paths("UNIQUE_GOAL_XYZ", "")
    for req in fi.run_batch.call_args.args[0]:
        assert "UNIQUE_GOAL_XYZ" in req.prompt


def test_paths_are_generated_uncached():
    fi = _engine([_payload(5.0)] * 3)
    RecursiveSolver(inference=fi)._generate_reasoning_paths("g", "")
    assert fi.run_batch.call_args.kwargs["use_cache"] is False


def test_unreachable_model_scores_zero_so_nothing_wins_by_default():
    solver = RecursiveSolver(inference=_engine([None, None, None]))
    paths = solver._generate_reasoning_paths("g", "")
    assert all(p.score == 0.0 for p in paths)
    assert all(p.complexity_time == "unknown" for p in paths)


def test_malformed_json_does_not_crash_the_node():
    fi = MagicMock()
    fi.run_batch.side_effect = lambda reqs, **kw: [
        InferenceResult(success=True, content="not json at all", tag=r.tag)
        for r in reqs]
    paths = RecursiveSolver(inference=fi)._generate_reasoning_paths("g", "")
    assert len(paths) == 3
    assert all(p.score == 0.0 for p in paths)


def test_scores_are_clamped_to_range():
    solver = RecursiveSolver(inference=_engine(
        [_payload(99.0), _payload(-5.0), _payload(5.0)]))
    scores = [p.score for p in solver._generate_reasoning_paths("g", "")]
    assert scores == [10.0, 0.0, 5.0]


def test_a_tie_is_reported_not_hidden():
    """All-equal scores mean the model did not discriminate; say so."""
    solver = RecursiveSolver()
    mk = lambda i, sc: ReasoningPath(path_id="path_" + i, name=i, strategy="", score=sc)
    solver._cross_evaluate_paths([mk("a", 8.0), mk("b", 8.0), mk("c", 8.0)])
    assert solver.last_evaluation_was_tied is True
    assert solver.last_tied_paths == ["path_a", "path_b", "path_c"]

    solver._cross_evaluate_paths([mk("a", 9.0), mk("b", 7.0), mk("c", 7.0)])
    assert solver.last_evaluation_was_tied is False


def test_evaluating_no_paths_is_an_error_not_a_silent_pick():
    try:
        RecursiveSolver()._cross_evaluate_paths([])
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty path list")
