import pytest

from saleha.core.benchmark_reporter import BenchmarkRun, BenchmarkReporter

def test_record_run():
    reporter = BenchmarkReporter()
    run = reporter.record_run("GPT-4o", "swe_bench", 10, 8)
    assert isinstance(run, BenchmarkRun)

def test_load_runs():
    reporter = BenchmarkReporter()
    runs = reporter.load_runs()
    assert len(runs) > 0

def test_best_score():
    reporter = BenchmarkReporter()
    best = reporter.best_score()
    assert isinstance(best, float)

def test_generate_leaderboard_report():
    reporter = BenchmarkReporter()
    report = reporter.generate_leaderboard_report()
    assert "🏆 SWE-bench Verified Leaderboard" in report
    assert "🤖 Saleha AI (local, $0)" in report

def test_generate_badge_markdown():
    reporter = BenchmarkReporter()
    badge = reporter.generate_badge_markdown()
    assert "![SWE-bench](https://img.shields.io/badge/SWE--bench-Not%20Run-lightgrey.svg)" not in badge