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
