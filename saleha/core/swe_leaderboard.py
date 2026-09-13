"""Saleha Core: run the local task benchmark and record the score.

## What this used to do

It reported a 100% pass rate, every time, for every model, without calling
one:

    def _generate_fix(self, task):
        \"\"\"Generate a fix using rule-based analysis (offline, no LLM needed).\"\"\"
        return task.get("expected_fix", task["buggy_code"])

That is the answer key. `_evaluate_fix` then `exec`'d the answer key against
the task's own test, which of course passed. `saleha benchmark-public`
printed the result as "pass@1" beside real published figures for Devin and
GPT-4o, and `saleha swe-export` wrote it into the **official SWE-bench
submission format** as "Pass@1 Rate: 100.00%".

## What it does now

Calls `real_task_bench.run_benchmark()`, which sends each task's prompt to a
real local model, strips the model's own demo code, executes the result in a
subprocess against a test that has been verified to fail on wrong code, and
reports what actually passed. A model that is unreachable produces a failure
with its transport error, not a default.

The name is kept for its callers but the module no longer claims any relation
to SWE-bench: it runs twelve small self-contained problems, and says so.
Scored SWE-bench needs infrastructure this machine does not currently have --
`real_task_bench.scored_swebench_availability()` reports exactly what is
missing rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from saleha.core.benchmark_reporter import BenchmarkReporter, BenchmarkRun
from saleha.core.real_task_bench import (
    DEFAULT_MODEL,
    TASKS,
    BenchRunReport,
    run_benchmark,
    verify_tests_can_fail,
)


@dataclass
class TaskResult:
    task_id: str
    solved: bool
    fix_applied: str
    time_sec: float
    error: str = ""


class LocalTaskBenchmark:
    """Runs the real local task suite and records the run."""

    def __init__(self, reporter: Optional[BenchmarkReporter] = None):
        self.reporter = reporter or BenchmarkReporter()

    def run_suite(self, model: str = DEFAULT_MODEL,
                  limit: Optional[int] = None,
                  on_task=None) -> BenchmarkRun:
        """Run every task against a real model and record the result.

        A run that refuses to start (because a test cannot fail) or whose
        model was unreachable is recorded with its real solved count -- zero
        -- never with a default.
        """
        report: BenchRunReport = run_benchmark(model=model, limit=limit,
                                               on_task=on_task)

        notes = report.summary_line()
        if not report.did_run:
            notes = f"REFUSED: {report.refused_reason}"

        return self.reporter.record_run(
            model=model,
            suite="local_tasks",
            total=report.total,
            solved=report.passed,
            avg_time_sec=(report.total_sec / report.total) if report.total else 0.0,
            notes=notes,
            metadata={
                "did_run": report.did_run,
                "benchmark": "saleha local_tasks (not SWE-bench)",
                "results": [
                    {
                        "task_id": o.task_id,
                        "solved": o.passed,
                        "duration_sec": o.duration_sec,
                        "error": o.error,
                        "patch": o.code,
                    }
                    for o in report.outcomes
                ],
            },
        )

    def task_results(self, run: BenchmarkRun) -> List[TaskResult]:
        """The per-task detail of a recorded run, for the exporter."""
        out: List[TaskResult] = []
        for item in (run.metadata or {}).get("results", []):
            out.append(TaskResult(
                task_id=item.get("task_id", "unknown"),
                solved=bool(item.get("solved")),
                fix_applied=item.get("patch", ""),
                time_sec=float(item.get("duration_sec", 0.0)),
                error=item.get("error", ""),
            ))
        return out

    def preflight(self) -> Dict[str, Any]:
        """Which tests cannot fail, if any. A benchmark whose tests always
        pass measures nothing, so this is checked before every run."""
        broken = verify_tests_can_fail()
        return {
            "total_tasks": len(TASKS),
            "tests_that_cannot_fail": broken,
            "usable": not broken,
        }

    def leaderboard_text(self) -> str:
        return self.reporter.generate_leaderboard_report()


local_benchmark = LocalTaskBenchmark()
