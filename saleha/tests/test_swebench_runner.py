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

    def test_assertion_only_passes_against_actually_generated_code(self):
        # A regression guard for the bug this module used to have: the
        # sandbox used to pre-define "safe_divide" as a correct
        # implementation regardless of what was generated, so this exact
        # assertion always passed. It must now fail when nothing defines
        # safe_divide, and pass when mock_generated_code actually does.
        unresolved_task = SWEBenchTask(
            instance_id="rigged-if-hardcoded",
            repo_name="test/repo",
            problem_statement="needs a real implementation",
            test_assertion="assert safe_divide(10, 0) == 0.0",
        )
        self.assertFalse(self.runner.evaluate_task(unresolved_task).resolved)

        resolved_task = SWEBenchTask(
            instance_id="genuinely-resolved",
            repo_name="test/repo",
            problem_statement="needs a real implementation",
            test_assertion="assert safe_divide(10, 0) == 0.0",
            mock_generated_code="def safe_divide(a, b):\n    return 0.0 if b == 0 else a / b\n",
        )
        self.assertTrue(self.runner.evaluate_task(resolved_task).resolved)


if __name__ == "__main__":
    unittest.main()
