"""
Saleha Core: Autonomous Benchmark & Evaluation Harness (SiliconCopilot-Eval)

Runs standardized software engineering benchmarks to measure model accuracy,
self-healing capability, pass@1 and pass@k rates, and token efficiency.
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

from saleha.orchestrator import SalehaOrchestrator
from saleha.core.recursive_solver import RecursiveSolver


@dataclass
class BenchmarkTask:
    """Represents an individual evaluation task."""
    task_id: str
    name: str
    category: str  # "algorithm", "bugfix", "security", "multifile"
    goal: str
    difficulty: str = "medium"  # "easy", "medium", "hard"
    expected_keywords: List[str] = field(default_factory=list)


@dataclass
class TaskEvalResult:
    """Evaluation result for a single task."""
    task_id: str
    name: str
    passed: bool
    attempts_required: int
    duration_sec: float
    error: str = ""


@dataclass
class BenchmarkSummary:
    """Aggregated evaluation benchmark report."""
    total_tasks: int
    passed_tasks: int
    pass_at_1_rate: float
    pass_at_k_rate: float
    average_duration_sec: float
    results: List[TaskEvalResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class BenchmarkHarness:
    """Autonomous benchmark runner for continuous evaluation of AI agent performance."""

    BUILTIN_SUITE = [
        BenchmarkTask(
            task_id="ALGO_01",
            name="Fibonacci Memoized Sequence",
            category="algorithm",
            goal="Write a fast memoized Fibonacci function in Python that handles n=100 without recursion error.",
            difficulty="easy",
            expected_keywords=["def fib", "memo"],
        ),
        BenchmarkTask(
            task_id="ALGO_02",
            name="LRU Cache Implementation",
            category="algorithm",
            goal="Implement an LRU Cache class with get and put methods in O(1) time complexity.",
            difficulty="medium",
            expected_keywords=["class LRUCache", "get", "put"],
        ),
        BenchmarkTask(
            task_id="SEC_01",
            name="SQL Injection Remediation",
            category="security",
            goal="Write a secure SQLite user query function that avoids SQL injection using bind parameters.",
            difficulty="medium",
            expected_keywords=["cursor.execute", "?"],
        ),
        BenchmarkTask(
            task_id="FIX_01",
            name="Zero Division & Type Validation Bugfix",
            category="bugfix",
            goal="Write a robust safe_divide(a, b) function that validates inputs and raises ValueError on zero divisor.",
            difficulty="easy",
            expected_keywords=["safe_divide", "ValueError"],
        ),
    ]

    def __init__(self, model: str = "auto", output_dir: str = ".saleha/benchmarks"):
        """Initializes the benchmark harness."""
        self.model = model
        self.output_dir = output_dir

    def run_suite(self, tasks: Optional[List[BenchmarkTask]] = None) -> BenchmarkSummary:
        """Executes evaluation across all tasks in the benchmark suite."""
        suite = tasks or self.BUILTIN_SUITE
        results: List[TaskEvalResult] = []
        pass_1_count = 0
        pass_k_count = 0
        total_time = 0.0

        for task in suite:
            t_start = time.time()
            passed = False
            attempts = 1
            err_msg = ""

            try:
                orchestrator = SalehaOrchestrator(model=self.model, max_healing_attempts=2)
                res = orchestrator.execute_task(task.goal)
                passed = res.success
                attempts = res.attempts or 1
                if not passed:
                    err_msg = "Task execution failed tests"
            except Exception as e:
                passed = False
                err_msg = str(e)

            duration = round(time.time() - t_start, 2)
            total_time += duration

            if passed:
                pass_k_count += 1
                if attempts == 1:
                    pass_1_count += 1

            results.append(TaskEvalResult(
                task_id=task.task_id,
                name=task.name,
                passed=passed,
                attempts_required=attempts,
                duration_sec=duration,
                error=err_msg,
            ))

        total_tasks = len(suite)
        pass_at_1 = round(pass_1_count / total_tasks * 100, 1) if total_tasks else 0.0
        pass_at_k = round(pass_k_count / total_tasks * 100, 1) if total_tasks else 0.0
        avg_dur = round(total_time / total_tasks, 2) if total_tasks else 0.0

        summary = BenchmarkSummary(
            total_tasks=total_tasks,
            passed_tasks=pass_k_count,
            pass_at_1_rate=pass_at_1,
            pass_at_k_rate=pass_at_k,
            average_duration_sec=avg_dur,
            results=results,
        )

        self.save_report(summary)
        return summary

    def save_report(self, summary: BenchmarkSummary):
        """Saves evaluation results to JSON and Markdown format."""
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            json_path = os.path.join(self.output_dir, "benchmark_results.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(asdict(summary), f, indent=2)

            md_path = os.path.join(self.output_dir, "BENCHMARK_REPORT.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(self.render_markdown(summary))
        except (OSError, IOError):
            pass  # noqa

    def render_markdown(self, summary: BenchmarkSummary) -> str:
        """Renders the benchmark summary report as clean GitHub Flavored Markdown."""
        lines = [
            "# 📊 Saleha Autonomous Benchmark Report",
            f"- **Total Tasks Evaluated**: {summary.total_tasks}",
            f"- **Pass@1 Rate**: `{summary.pass_at_1_rate}%`",
            f"- **Pass@k (Self-Healed) Rate**: `{summary.pass_at_k_rate}%`",
            f"- **Average Duration**: `{summary.average_duration_sec}s`\n",
            "| Task ID | Name | Status | Attempts | Duration |",
            "| :--- | :--- | :---: | :---: | :---: |",
        ]
        for r in summary.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            lines.append(f"| `{r.task_id}` | {r.name} | {status} | {r.attempts_required} | {r.duration_sec}s |")
        return "\n".join(lines)


benchmark_harness = BenchmarkHarness()


if __name__ == "__main__":
    _harness = BenchmarkHarness()
    _rep = _harness.run_suite([BenchmarkHarness.BUILTIN_SUITE[0]])
