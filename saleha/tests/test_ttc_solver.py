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
    assert result.passed is True


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
