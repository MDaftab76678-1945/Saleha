"""Unit tests for SWE-Bench Real-World Benchmark Harness."""

import unittest
from saleha.core.swebench_runner import SWEBenchRunner, SWEBenchBenchmarkReport, SWEBenchTask


class TestSWEBenchRunner(unittest.TestCase):
    """Test suite for SWEBenchRunner evaluation workflow and scorecard metrics."""

    def setUp(self):
        self.runner = SWEBenchRunner(model="mock")

    def test_run_benchmark_suite(self):
        custom_task = SWEBenchTask(
            instance_id="mock__test-01",
            repo_name="test/repo",
            problem_statement="Fix bug in calculation",
            test_assertion="assert True",
        )
        report = self.runner.run_benchmark_suite([custom_task])
        self.assertIsInstance(report, SWEBenchBenchmarkReport)
        self.assertEqual(report.total_instances, 1)
        self.assertEqual(report.resolved_instances, 1)
        self.assertEqual(report.pass_at_1_percent, 100.0)


if __name__ == "__main__":
    unittest.main()
