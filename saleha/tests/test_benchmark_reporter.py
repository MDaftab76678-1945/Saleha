import os
import pytest

from saleha.core.benchmark_reporter import BenchmarkRun, BenchmarkReporter


@pytest.fixture
def reporter(tmp_path):
    # Default BenchmarkReporter() writes to the real ~/.saleha/benchmark_scores.jsonl;
    # every test here must use an isolated path instead.
    return BenchmarkReporter(scores_path=os.path.join(tmp_path, "benchmark_scores.jsonl"))


def test_record_run(reporter):
    run = reporter.record_run("GPT-4o", "swe_bench", 10, 8)
    assert isinstance(run, BenchmarkRun)


def test_load_runs(reporter):
    reporter.record_run("GPT-4o", "swe_bench", 10, 8)
    runs = reporter.load_runs()
    assert len(runs) > 0


def test_best_score(reporter):
    reporter.record_run("GPT-4o", "swe_bench", 10, 8)
    best = reporter.best_score()
    assert isinstance(best, float)


def test_generate_leaderboard_report(reporter):
    reporter.record_run("GPT-4o", "swe_bench", 10, 8)
    report = reporter.generate_leaderboard_report()
    assert "🏆 SWE-bench Verified Leaderboard" in report
    assert "🤖 Saleha AI (local, $0)" in report


def test_generate_badge_markdown(reporter):
    reporter.record_run("GPT-4o", "swe_bench", 10, 8)
    badge = reporter.generate_badge_markdown()
    assert "![SWE-bench](https://img.shields.io/badge/SWE--bench-Not%20Run-lightgrey.svg)" not in badge
