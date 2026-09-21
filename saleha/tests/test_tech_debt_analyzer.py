"""Unit tests for Technical Debt & Cognitive Complexity De-Synthesizer."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.tech_debt_analyzer import TechDebtAnalyzer


class TechDebtAnalyzerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.analyzer = TechDebtAnalyzer(root_dir=self.temp_dir)

        # Create a sample complex function
        self.sample_file = os.path.join(self.temp_dir, "complex_module.py")
        with open(self.sample_file, "w", encoding="utf-8") as f:
            f.write("""
def deeply_nested_logic(data):
    total = 0
    if data:
        for item in data:
            if item > 10:
                if item % 2 == 0:
                    total += item
    return total
""")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_file_computes_complexity_and_nesting(self) -> None:
        metrics = self.analyzer.analyze_file(self.sample_file)
        self.assertEqual(len(metrics), 1)
        m = metrics[0]
        self.assertEqual(m.function_name, "deeply_nested_logic")
        self.assertGreaterEqual(m.cyclomatic_complexity, 4)
        self.assertGreaterEqual(m.max_nesting_depth, 3)

    def test_analyze_workspace(self) -> None:
        rep = self.analyzer.analyze_workspace(root_dir=self.temp_dir, threshold=3)
        self.assertEqual(rep.total_functions_analyzed, 1)
        self.assertGreaterEqual(rep.hotspots_count, 1)

    def test_nested_function_complexity_is_not_double_counted_into_outer(self) -> None:
        """Real bug found auditing this module: analyze_file() calls
        ast.walk(tree) at module level, so a nested function is visited and
        scored on its own -- but _ComplexityVisitor's generic_visit also
        descended into that same nested function while scoring the OUTER
        function, double-counting its branches. Confirmed by direct probe
        before fixing: an outer function whose own logic has one real `if`
        (true complexity 2) scored 4 because a nested helper's two `if`s
        got added on top."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nested.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "def outer():\n"
                    "    if True:\n"
                    "        pass\n"
                    "    def inner():\n"
                    "        if True:\n"
                    "            pass\n"
                    "        if True:\n"
                    "            pass\n"
                    "    return inner\n"
                )
            analyzer = TechDebtAnalyzer(root_dir=d)
            metrics = {m.function_name: m for m in analyzer.analyze_file(path)}
            self.assertEqual(len(metrics), 2)
            self.assertEqual(metrics["outer"].cyclomatic_complexity, 2)
            self.assertEqual(metrics["inner"].cyclomatic_complexity, 3)

    def test_empty_workspace_reports_zero_not_vacuous_one(self) -> None:
        """An empty workspace has zero complexity -- reporting 1.0 would be
        the vacuous-metric distortion this project forbids."""
        with tempfile.TemporaryDirectory() as d:
            rep = TechDebtAnalyzer(root_dir=d).analyze_workspace()
        self.assertEqual(rep.total_functions_analyzed, 0)
        self.assertEqual(rep.average_cyclomatic, 0.0)
        self.assertEqual(rep.max_cyclomatic, 0)
        self.assertEqual(rep.hotspots_count, 0)

    def test_ternary_expression_counts_one_branch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tern.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("def pick(a):\n    return 1 if a else 2\n")
            metrics = TechDebtAnalyzer(root_dir=d).analyze_file(path)
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].cyclomatic_complexity, 2)

    def test_comprehension_counts_loop_and_condition(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "comp.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("def keep(xs):\n    return [x for x in xs if x]\n")
            metrics = TechDebtAnalyzer(root_dir=d).analyze_file(path)
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].cyclomatic_complexity, 3)

    def test_match_counts_each_case_arm(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "def kind(x):\n"
                    "    match x:\n"
                    "        case 1:\n"
                    "            return 'one'\n"
                    "        case 2:\n"
                    "            return 'two'\n"
                    "        case _:\n"
                    "            return 'other'\n"
                )
            metrics = TechDebtAnalyzer(root_dir=d).analyze_file(path)
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].cyclomatic_complexity, 4)


if __name__ == "__main__":
    unittest.main()

