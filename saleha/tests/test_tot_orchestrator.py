"""
Unit tests for TreeOfThoughtsOrchestrator and Self-Evolving Heuristics in Saleha v2.6.0
"""

import unittest
import shutil
import tempfile
from pathlib import Path

from saleha.core.tot_orchestrator import TreeOfThoughtsOrchestrator, ThoughtNode, ToTResult


class TreeOfThoughtsOrchestratorTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tot = TreeOfThoughtsOrchestrator(memory_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_node_passing_code(self):
        code = "def add(a, b): return a + b"
        tests = "assert add(2, 3) == 5\nassert add(-1, 1) == 0"
        score, passed, out = self.tot.evaluate_code_node(code, tests)
        self.assertTrue(passed)
        self.assertGreaterEqual(score, 0.9)

    def test_evaluate_node_failing_code(self):
        code = "def add(a, b): return a - b"
        tests = "assert add(2, 3) == 5"
        score, passed, out = self.tot.evaluate_code_node(code, tests)
        self.assertFalse(passed)
        self.assertLess(score, 0.9)

    def test_evaluate_node_syntax_error(self):
        code = "def broken(:"
        tests = "assert True"
        score, passed, out = self.tot.evaluate_code_node(code, tests)
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    def test_solve_task_with_tot_root_success(self):
        goal = "Implement multiply function"
        code = "def multiply(a, b): return a * b"
        tests = "assert multiply(3, 4) == 12"
        res: ToTResult = self.tot.solve_task_with_tot(goal, code, tests, max_depth=2, branching_factor=2)
        self.assertTrue(res.success)
        self.assertEqual(res.total_nodes_explored, 1)
        self.assertEqual(len(res.winning_path), 1)

    def test_record_and_get_learned_heuristics(self):
        self.tot.record_learned_heuristic("zero_div", "Guard against zero denominator", "divide function")
        heuristics = self.tot.get_learned_heuristics()
        self.assertEqual(len(heuristics), 1)
        self.assertEqual(heuristics[0]["bug_type"], "zero_div")
        self.assertEqual(heuristics[0]["rule"], "Guard against zero denominator")


if __name__ == "__main__":
    unittest.main()
