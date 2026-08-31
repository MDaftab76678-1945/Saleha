"""Tests for SWE-bench Leaderboard Runner and Benchmark Reporter."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.benchmark_reporter import BenchmarkReporter, PUBLIC_LEADERBOARD
from saleha.core.swe_leaderboard import SWELeaderboard, BUILTIN_TASKS, TaskResult


class BenchmarkReporterTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reporter = BenchmarkReporter(
            scores_path=os.path.join(self.tmp, "scores.jsonl")
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_and_load_run(self):
        run = self.reporter.record_run(
            model="qwen2.5-coder:7b", suite="swe_bench",
            total=10, solved=3, avg_time_sec=5.2
        )
        self.assertEqual(run.score_pct, 30.0)
        loaded = self.reporter.load_runs()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].model, "qwen2.5-coder:7b")

    def test_filter_by_suite(self):
        self.reporter.record_run("m1", "swe_bench", 10, 3)
        self.reporter.record_run("m2", "humaneval", 10, 8)
        swe_runs = self.reporter.load_runs(suite="swe_bench")
        self.assertEqual(len(swe_runs), 1)
        self.assertEqual(swe_runs[0].suite, "swe_bench")

    def test_best_score(self):
        self.reporter.record_run("m1", "swe_bench", 10, 2)   # 20%
        self.reporter.record_run("m2", "swe_bench", 10, 5)   # 50%
        self.reporter.record_run("m3", "swe_bench", 10, 3)   # 30%
        self.assertEqual(self.reporter.best_score("swe_bench"), 50.0)

    def test_best_score_no_runs(self):
        self.assertIsNone(self.reporter.best_score())

    def test_leaderboard_report_contains_competitors(self):
        self.reporter.record_run("saleha", "swe_bench", 100, 25)  # 25%
        report = self.reporter.generate_leaderboard_report()
        self.assertIn("Devin", report)
        self.assertIn("Saleha", report)
        self.assertIn("25.00", report)

    def test_badge_markdown_no_runs(self):
        badge = self.reporter.generate_badge_markdown()
        self.assertIn("Not%20Run", badge)

    def test_badge_markdown_with_score(self):
        self.reporter.record_run("m", "swe_bench", 100, 30)
        badge = self.reporter.generate_badge_markdown("swe_bench")
        self.assertIn("30.0", badge)
        self.assertIn("img.shields.io", badge)

    def test_public_leaderboard_has_entries(self):
        self.assertIn("Devin (Cognition)", PUBLIC_LEADERBOARD)
        self.assertGreater(PUBLIC_LEADERBOARD["Devin (Cognition)"], 0)

    def test_pass_at_1_property(self):
        run = self.reporter.record_run("m", "swe_bench", 10, 4)
        self.assertEqual(run.pass_at_1, run.score_pct)


class SWELeaderboardTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reporter = BenchmarkReporter(
            scores_path=os.path.join(self.tmp, "scores.jsonl")
        )
        self.leaderboard = SWELeaderboard(reporter=self.reporter)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_builtin_tasks_defined(self):
        self.assertGreater(len(BUILTIN_TASKS), 0)
        for task in BUILTIN_TASKS:
            self.assertIn("task_id", task)
            self.assertIn("buggy_code", task)
            self.assertIn("test_code", task)
            self.assertIn("expected_fix", task)

    def test_run_suite_returns_benchmark_run(self):
        run = self.leaderboard.run_suite(use_llm=False)
        self.assertIsNotNone(run)
        self.assertEqual(run.suite, "swe_bench")
        self.assertEqual(run.total_tasks, len(BUILTIN_TASKS))

    def test_all_builtin_tasks_solvable(self):
        run = self.leaderboard.run_suite(use_llm=False)
        self.assertEqual(run.solved, len(BUILTIN_TASKS),
                         f"Expected all {len(BUILTIN_TASKS)} tasks solved, got {run.solved}")
        self.assertEqual(run.score_pct, 100.0)

    def test_evaluate_fix_correct(self):
        task = BUILTIN_TASKS[0]
        self.assertTrue(self.leaderboard._evaluate_fix(task, task["expected_fix"]))

    def test_evaluate_fix_buggy_fails(self):
        task = BUILTIN_TASKS[0]
        self.assertFalse(self.leaderboard._evaluate_fix(task, task["buggy_code"]))

    def test_leaderboard_text_format(self):
        self.leaderboard.run_suite(use_llm=False)
        text = self.leaderboard.leaderboard_text()
        self.assertIn("SWE-bench", text)
        self.assertIn("Saleha", text)

    def test_custom_task_list(self):
        custom = [{
            "task_id": "custom-001",
            "description": "Simple add fix",
            "buggy_code": "def add(a, b): return a - b",
            "test_code": "assert add(2, 3) == 5",
            "expected_fix": "def add(a, b): return a + b",
        }]
        run = self.leaderboard.run_suite(tasks=custom, use_llm=False)
        self.assertEqual(run.total_tasks, 1)
        self.assertEqual(run.solved, 1)


if __name__ == "__main__":
    unittest.main()
