"""Unit tests for Autonomous Benchmark & Evaluation Harness."""

import unittest
import tempfile
import shutil
from saleha.core.benchmark_harness import BenchmarkHarness, BenchmarkTask, BenchmarkSummary


class TestBenchmarkHarness(unittest.TestCase):
    """Test suite for BenchmarkHarness evaluation metrics and task suites."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.harness = BenchmarkHarness(model="mock", output_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_builtin_suite_integrity(self):
        self.assertTrue(len(self.harness.BUILTIN_SUITE) >= 4)
        task_ids = {t.task_id for t in self.harness.BUILTIN_SUITE}
        self.assertIn("ALGO_01", task_ids)
        self.assertIn("SEC_01", task_ids)

    def test_render_markdown(self):
        summary = BenchmarkSummary(
            total_tasks=2,
            passed_tasks=2,
            pass_at_1_rate=100.0,
            pass_at_k_rate=100.0,
            average_duration_sec=1.2,
            results=[],
        )
        md = self.harness.render_markdown(summary)
        self.assertIn("# 📊 Saleha Autonomous Benchmark Report", md)
        self.assertIn("100.0%", md)


if __name__ == "__main__":
    unittest.main()
