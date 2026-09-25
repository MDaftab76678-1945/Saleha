"""
Saleha Harness: Statistical Metrics & Pass@k Estimators

Implements the standard unbiased Pass@k estimator (HumanEval) and the per-suite
aggregation the harness reports.

What the harness reports is Pass@1 only. It draws ONE sample per task, and
Pass@k for k > 1 needs n >= k samples of the *same* task. Feeding it the
number of distinct tasks instead (as this module once did) reported "Pass@5 =
100%" for any run where fewer than five tasks failed.

A task that did not execute -- replayed from memory, blocked by the sandbox,
no code generated, harness error -- is counted as not executed, never as a
pass and never as a fail. Pass@1 is computed over executed tasks only and is
None when nothing executed.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional


def estimate_pass_at_k(num_samples: int, num_correct: int, k: int = 1) -> float:
    """
    Estimates unbiased Pass@k for ONE task from `num_samples` samples of it:
    Pass@k = 1 - (comb(n - c, k) / comb(n, k))
    """
    if num_samples <= 0 or k <= 0 or k > num_samples:
        return 0.0
    if num_correct >= num_samples:
        return 1.0
    if num_correct <= 0:
        return 0.0

    # If remaining incorrect samples (n - c) is less than k, pass rate is 1.0
    if (num_samples - num_correct) < k:
        return 1.0

    comb_n_k = math.comb(num_samples, k)
    comb_nc_k = math.comb(num_samples - num_correct, k)
    return round(1.0 - (comb_nc_k / comb_n_k), 4)


@dataclass
class HarnessTaskResult:
    task_id: str
    benchmark: str
    prompt: str
    passed: bool
    attempts_used: int = 1
    latency_sec: float = 0.0
    error_detail: Optional[str] = None
    # False when the task's tests never ran against model-generated code.
    # `passed` is always False then, and `error_detail` says why.
    executed: bool = True


@dataclass
class BenchmarkSummary:
    benchmark_name: str
    total_tasks: int
    passed_tasks: int
    executed_tasks: int = 0
    pass_at_1: Optional[float] = None  # Percentage of executed tasks; None if none executed
    avg_latency_sec: float = 0.0
    task_results: List[HarnessTaskResult] = field(default_factory=list)


def pass_rate(passed: int, executed: int) -> Optional[float]:
    """Percentage passed of executed, or None -- never 0% or 100% for an empty set."""
    if executed <= 0:
        return None
    return round((passed / executed) * 100, 2)


def compute_benchmark_summary(benchmark_name: str, results: List[HarnessTaskResult]) -> BenchmarkSummary:
    """Aggregates raw task execution results into per-suite metrics."""
    executed = [r for r in results if r.executed]
    passed = sum(1 for r in executed if r.passed)
    avg_latency = round(sum(r.latency_sec for r in executed) / len(executed), 2) if executed else 0.0

    return BenchmarkSummary(
        benchmark_name=benchmark_name,
        total_tasks=len(results),
        passed_tasks=passed,
        executed_tasks=len(executed),
        pass_at_1=pass_rate(passed, len(executed)),
        avg_latency_sec=avg_latency,
        task_results=list(results),
    )
