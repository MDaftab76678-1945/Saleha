"""Unit tests for Technical Debt & Cognitive Complexity De-Synthesizer."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.tech_debt_analyzer import TechDebtAnalyzer, FunctionComplexityMetric, CodebaseDebtReport


class TechDebtAnalyzerTests(unittest.TestCase):

    def setUp(self):
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

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_file_computes_complexity_and_nesting(self):
        metrics = self.analyzer.analyze_file(self.sample_file)
        self.assertEqual(len(metrics), 1)
        m = metrics[0]
        self.assertEqual(m.function_name, "deeply_nested_logic")
        self.assertGreaterEqual(m.cyclomatic_complexity, 4)
        self.assertGreaterEqual(m.max_nesting_depth, 3)

    def test_analyze_workspace(self):
        rep = self.analyzer.analyze_workspace(root_dir=self.temp_dir, threshold=3)
        self.assertEqual(rep.total_functions_analyzed, 1)
        self.assertGreaterEqual(rep.hotspots_count, 1)


if __name__ == "__main__":
    unittest.main()

