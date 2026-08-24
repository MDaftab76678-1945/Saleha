"""Unit tests for Saleha Model Benchmark Evaluator."""

import unittest
from saleha.core.evaluator import ModelBenchmarkEvaluator, BenchmarkTask


class EvaluatorTests(unittest.TestCase):

    def setUp(self):
        self.custom_tasks = [
            BenchmarkTask(
                task_id="TEST001",
                prompt="Write a function add(a, b)",
                test_suite="assert add(2, 3) == 5\nprint('TEST_PASSED')"
            )
        ]
        self.evaluator = ModelBenchmarkEvaluator(tasks=self.custom_tasks)

    def test_evaluator_dry_run(self):
        score = self.evaluator.run_benchmark(model="mock-model", dry_run=True)
        self.assertEqual(score.model, "mock-model")
        self.assertEqual(score.total_tasks, 1)
        self.assertEqual(score.passed_tasks, 1)
        self.assertEqual(score.pass_rate, 100.0)
        self.assertEqual(len(score.task_results), 1)
        self.assertTrue(score.task_results[0]["passed"])


if __name__ == "__main__":
    unittest.main()

