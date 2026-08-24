"""Unit tests for Saleha Harness (DeepSeek-Standard Evaluation Framework)."""

import os
import shutil
import tempfile
import unittest
from click.testing import CliRunner

from saleha.harness.metrics import estimate_pass_at_k, HarnessTaskResult, compute_benchmark_summary
from saleha.harness.benchmarks import BenchmarkCatalog, BenchmarkTaskSpec
from saleha.harness.reporter import HarnessReporter, HarnessReport, BenchmarkSummary
from saleha.harness.core import SalehaHarness
from saleha.cli.commands import cli


class SalehaHarnessTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_harness_test_")
        self.history_file = os.path.join(self.temp_dir, "test_harness_history.json")
        self.reporter = HarnessReporter(history_path=self.history_file)
        self.harness = SalehaHarness()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unbiased_pass_at_k_calculation(self):
        # 10 samples, 10 correct -> pass@1 = 1.0, pass@5 = 1.0
        self.assertEqual(estimate_pass_at_k(10, 10, k=1), 1.0)
        self.assertEqual(estimate_pass_at_k(10, 10, k=5), 1.0)

        # 10 samples, 0 correct -> pass@1 = 0.0, pass@5 = 0.0
        self.assertEqual(estimate_pass_at_k(10, 0, k=1), 0.0)

        # 10 samples, 5 correct -> pass@1 = 0.5
        p1 = estimate_pass_at_k(10, 5, k=1)
        self.assertEqual(p1, 0.5)

        # Invalid cases return 0.0
        self.assertEqual(estimate_pass_at_k(0, 0, k=1), 0.0)
        self.assertEqual(estimate_pass_at_k(5, 2, k=10), 0.0)

    def test_benchmark_catalog_retrieval(self):
        catalogs = BenchmarkCatalog.list_available_benchmarks()
        self.assertIn("humaneval_plus", catalogs)
        self.assertIn("mbpp_plus", catalogs)
        self.assertIn("math_reasoning", catalogs)
        self.assertIn("swe_repo", catalogs)
        self.assertIn("tool_use", catalogs)

        all_tasks = BenchmarkCatalog.get_benchmarks("all")
        self.assertTrue(len(all_tasks) >= 9)

    def test_harness_dry_run_evaluation(self):
        report = self.harness.evaluate(model="mock-qwen-coder", benchmark="all", dry_run=True)
        self.assertEqual(report.model_name, "mock-qwen-coder")
        self.assertEqual(report.overall_pass_at_1, 100.0)
        self.assertTrue(len(report.benchmark_summaries) >= 4)

    def test_reporter_save_load_and_export(self):
        report = HarnessReport(
            model_name="qwen2.5-coder:1.5b",
            timestamp="2026-08-24 22:00:00",
            total_tasks=10,
            overall_pass_at_1=90.0,
            overall_pass_at_5=95.0,
            avg_latency_sec=0.25,
            avg_tokens_per_sec=120.0,
            benchmark_summaries={
                "humaneval_plus": BenchmarkSummary(
                    benchmark_name="humaneval_plus",
                    total_tasks=3,
                    passed_tasks=3,
                    pass_at_1=100.0
                )
            }
        )

        ok = self.reporter.save_report(report)
        self.assertTrue(ok)

        history = self.reporter.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["model"], "qwen2.5-coder:1.5b")

        export_file = os.path.join(self.temp_dir, "report.md")
        exp_ok = self.reporter.export_markdown(report, export_file)
        self.assertTrue(exp_ok)
        self.assertTrue(os.path.isfile(export_file))

    def test_cli_harness_commands(self):
        runner = CliRunner()

        # 1. Test harness list
        res_list = runner.invoke(cli, ["harness", "list", "--json"])
        self.assertEqual(res_list.exit_code, 0)

        # 2. Test harness run dry-run
        res_run = runner.invoke(cli, ["harness", "run", "--benchmark", "mbpp_plus", "--dry-run", "--json"])
        self.assertEqual(res_run.exit_code, 0)


if __name__ == "__main__":
    unittest.main()

