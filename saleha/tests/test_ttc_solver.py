"""
Unit tests for Saleha Test-Time Compute (TTC) Multi-Trajectory Solver
(saleha/core/ttc_solver.py).
"""

from saleha.core.ttc_solver import (
    TTCTrajectorySolver,
    CandidateTrajectory,
    TTCSolveResult,
    ttc_solver,
)


def test_ttc_reranks_and_picks_cleanest():
    solver = TTCTrajectorySolver()

    # Candidate 1: Syntax error
    c1 = CandidateTrajectory(
        trajectory_id="C1",
        strategy_name="broken",
        code="def bad_syntax(: return 1",
        explanation="Broken syntax attempt",
    )

    # Candidate 2: Untyped and bare except
    c2 = CandidateTrajectory(
        trajectory_id="C2",
        strategy_name="naive",
        code="""
def compute(x):
    try:
        return x * 2
    except:
        return 0
""",
        explanation="Naive untyped implementation",
    )

    # Candidate 3: Clean, typed, documented
    c3 = CandidateTrajectory(
        trajectory_id="C3",
        strategy_name="production_grade",
        code="""
def compute(x: int) -> int:
    \"\"\"Computes double of integer.\"\"\"
    return x * 2
""",
        explanation="Production grade typed compute function",
    )

    result = solver.solve(
        problem="Implement compute(x: int) -> int",
        provided_candidates=[c1, c2, c3],
    )

    assert result.candidate_count == 3
    assert result.best_trajectory is not None
    assert result.best_trajectory.trajectory_id == "C3"
    assert result.best_trajectory.overall_score > c2.overall_score
    assert c2.overall_score > c1.overall_score
    # No test suite was supplied, so nothing was ever executed. `passed` means
    # "proved by running tests", not "scored well" -- ranking still works.
    assert result.passed is False


def test_ttc_with_test_code_verification():
    solver = TTCTrajectorySolver()

    # Candidate A: Wrong answer
    c_wrong = CandidateTrajectory(
        trajectory_id="A",
        strategy_name="incorrect",
        code="""
def add(a: int, b: int) -> int:
    return a - b
""",
        explanation="Subtract instead of add",
    )

    # Candidate B: Correct answer
    c_correct = CandidateTrajectory(
        trajectory_id="B",
        strategy_name="correct",
        code="""
def add(a: int, b: int) -> int:
    return a + b
""",
        explanation="Correctly adds two numbers",
    )

    test_code = """
import unittest

class TestAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
"""

    result = solver.solve(
        problem="Add two integers",
        test_code=test_code,
        provided_candidates=[c_wrong, c_correct],
    )

    assert result.best_trajectory is not None
    assert result.best_trajectory.trajectory_id == "B"
    assert result.best_trajectory.test_score == 100.0
    assert c_wrong.test_score == 0.0


def test_ttc_dynamic_generator_fn():
    solver = TTCTrajectorySolver()

    def mock_generator(problem: str, strategy: str):
        if "defensive" in strategy:
            return (
                f"def solve(val: int) -> int:\n    if val < 0:\n        raise ValueError()\n    return val\n",
                f"Defensive strategy checking bounds for {problem}",
            )
        return (
            f"def solve(val: int) -> int:\n    return val\n",
            f"Direct strategy for {problem}",
        )

    result = solver.solve(
        problem="Validate and return integer",
        candidate_generator_fn=mock_generator,
        num_candidates=3,
    )

    assert result.candidate_count == 3
    assert result.best_trajectory is not None
    assert "TTC Solver explored 3 trajectories" in result.summary


def test_ttc_brand_hygiene_penalty():
    solver = TTCTrajectorySolver()

    # Candidate with leaked foreign trademark
    c_leaked = CandidateTrajectory(
        trajectory_id="LEAK",
        strategy_name="foreign",
        code="""
def generate_code() -> str:
    # hermes system prompt
    return "ok"
""",
        explanation="Hermes model generation",
    )

    # Sovereign clean candidate
    c_clean = CandidateTrajectory(
        trajectory_id="CLEAN",
        strategy_name="sovereign",
        code="""
def generate_code() -> str:
    \"\"\"Saleha sovereign generator.\"\"\"
    return "ok"
""",
        explanation="Saleha native autonomous generation",
    )

    result = solver.solve(
        problem="Generate code safely",
        provided_candidates=[c_leaked, c_clean],
    )

    assert result.best_trajectory is not None
    assert result.best_trajectory.trajectory_id == "CLEAN"
    assert c_leaked.overall_score < c_clean.overall_score


# ---------------------------------------------------------------------------
# Regressions for the two bugs found auditing this module:
#   1. `/ttc <anything>` returned a hardcoded `return 'solved'` stub and scored
#      it 90/100 with passed=True, without ever calling a model.
#   2. The scorer rated EMPTY code 100.0 -- higher than real code (96.0) --
#      because the AST quality check finds no defects in nothing. Since the
#      reranker sorts descending, failed generations sorted to the TOP.
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock

from saleha.core.fast_inference import InferenceResult

GOOD_REPLY = "```python\ndef merge(a, b):\n    return sorted(a + b)\n```"
REAL_CODE = "def compute(x: int) -> int:\n    return x * 2\n"


def _fake_engine(contents):
    fi = MagicMock()
    fi.run_batch.side_effect = lambda reqs, **kw: [
        InferenceResult(success=bool(c), content=c or "",
                        error="" if c else "connection refused", tag=r.tag)
        for c, r in zip(contents, reqs)]
    return fi


def test_empty_code_scores_zero_not_one_hundred():
    solver = TTCTrajectorySolver()
    empty = CandidateTrajectory(trajectory_id="E", strategy_name="none",
                                code="", explanation="failed")
    real = CandidateTrajectory(trajectory_id="R", strategy_name="real",
                               code=REAL_CODE, explanation="works")
    e = solver.evaluate_candidate(empty)
    r = solver.evaluate_candidate(real)
    assert e.overall_score == 0.0
    assert e.metadata.get("rejected") == "empty code"
    # The whole point: real code must outrank a failed generation.
    assert r.overall_score > e.overall_score


def test_whitespace_only_code_is_also_rejected():
    solver = TTCTrajectorySolver()
    c = solver.evaluate_candidate(
        CandidateTrajectory(trajectory_id="W", strategy_name="ws",
                            code="   \n\t\n", explanation="blank"))
    assert c.overall_score == 0.0


def test_no_generator_calls_a_real_model_not_a_stub():
    fi = _fake_engine([GOOD_REPLY] * 3)
    res = TTCTrajectorySolver(inference=fi).solve(
        problem="merge two sorted lists", num_candidates=3)
    assert fi.run_batch.call_count == 1
    assert res.candidate_count == 3
    assert "return 'solved'" not in (res.best_trajectory.code or "")
    assert "def merge" in res.best_trajectory.code


def test_default_candidates_use_distinct_strategies():
    """Three samples of one prompt is best-of-N, not multi-trajectory."""
    fi = _fake_engine([GOOD_REPLY] * 3)
    TTCTrajectorySolver(inference=fi).solve(problem="p", num_candidates=3)
    prompts = [r.prompt for r in fi.run_batch.call_args.args[0]]
    assert len(set(prompts)) == 3


def test_default_candidates_are_generated_uncached():
    fi = _fake_engine([GOOD_REPLY] * 3)
    TTCTrajectorySolver(inference=fi).solve(problem="p", num_candidates=3)
    assert fi.run_batch.call_args.kwargs["use_cache"] is False


def test_unreachable_model_does_not_report_success():
    fi = _fake_engine([None, None, None])
    res = TTCTrajectorySolver(inference=fi).solve(problem="p", num_candidates=3)
    assert res.passed is False
    assert res.best_trajectory.overall_score == 0.0


def test_passed_requires_executed_tests_not_a_score():
    """`passed` used to be `overall_score >= 70`, true without running anything."""
    res = TTCTrajectorySolver().solve(
        problem="p",
        provided_candidates=[CandidateTrajectory(
            trajectory_id="C", strategy_name="s",
            code=REAL_CODE, explanation="ok")])
    assert res.best_trajectory.overall_score > 70.0
    assert res.passed is False        # nothing was ever executed
