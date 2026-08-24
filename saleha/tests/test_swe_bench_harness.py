"""Unit tests for SWE-Bench Verified Evaluation Harness."""

import unittest
from saleha.core.swe_bench_harness import SWEBenchHarness, SWEBenchTask


class SWEBenchTests(unittest.TestCase):

    def setUp(self):
        custom_task = SWEBenchTask(
            instance_id="SWE-TEST-001",
            repo="saleha/core",
            problem_statement="Fix dummy bug",
            base_code="def fix_me(): return 42\n",
            test_patch="assert fix_me() == 42\nprint('SWE_BENCH_VERIFIED')"
        )
        self.harness = SWEBenchHarness(tasks=[custom_task])

    def test_swe_bench_dry_run(self):
        report = self.harness.run_evaluation(dry_run=True)
        self.assertEqual(report.total_instances, 1)
        self.assertEqual(report.resolved_instances, 1)
        self.assertEqual(report.pass_rate, 100.0)

    def test_swe_bench_execution(self):
        report = self.harness.run_evaluation(dry_run=False)
        self.assertEqual(report.total_instances, 1)
        self.assertEqual(report.resolved_instances, 1)
        self.assertEqual(report.pass_rate, 100.0)
        self.assertTrue(report.results[0]["resolved"])


if __name__ == "__main__":
    unittest.main()

