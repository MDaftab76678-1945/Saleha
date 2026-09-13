import os
import pytest

from saleha.core.benchmark_reporter import BenchmarkRun, BenchmarkReporter


@pytest.fixture
def reporter(tmp_path):
    # Default BenchmarkReporter() writes to the real ~/.saleha/benchmark_scores.jsonl;
    # every test here must use an isolated path instead.
    return BenchmarkReporter(scores_path=os.path.join(tmp_path, "benchmark_scores.jsonl"))


def test_record_run(reporter):
    run = reporter.record_run("qwen2.5-coder:3b", "local_tasks", 10, 8)
    assert isinstance(run, BenchmarkRun)


def test_load_runs(reporter):
    reporter.record_run("qwen2.5-coder:3b", "local_tasks", 10, 8)
    runs = reporter.load_runs()
    assert len(runs) > 0


def test_best_score(reporter):
    # The default suite must match what the benchmark actually records, or
    # best_score() silently reports "no runs" for every real run.
    reporter.record_run("qwen2.5-coder:3b", "local_tasks", 10, 8)
    best = reporter.best_score()
    assert best == 80.0


def test_leaderboard_report_separates_our_score_from_published_figures(reporter):
    # This used to assert the single merged ranking, in which Saleha's row was
    # sorted among real published SWE-bench Verified scores and marked
    # " <- YOU" -- a rank on a benchmark this project has never run.
    reporter.record_run("qwen2.5-coder:3b", "local_tasks", 12, 9)
    report = reporter.generate_leaderboard_report()

    assert "Saleha local task benchmark" in report
    assert "75.00%" in report                      # 9/12, our real number
    assert "has NOT run" in report
    assert "not comparable" in report
    # The published figures are present as context, but never marked as a
    # rank against us.
    assert "Devin (Cognition)" in report
    assert "← YOU" not in report and "<- YOU" not in report


def test_leaderboard_report_with_no_runs_claims_no_score(reporter):
    report = reporter.generate_leaderboard_report()
    assert "No run recorded yet" in report


def test_generate_badge_markdown(reporter):
    reporter.record_run("qwen2.5-coder:3b", "local_tasks", 10, 8)
    badge = reporter.generate_badge_markdown()
    assert "Not%20Run" not in badge
    assert "80.0" in badge
