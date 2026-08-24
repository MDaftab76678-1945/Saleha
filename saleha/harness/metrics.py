"""
Saleha Harness: Statistical Metrics & Pass@k Estimators

Implements standard unbiased Pass@k combinatorial probability formulas (HumanEval / DeepSeek Harness standard),
latency meters, token throughput metrics, and self-healing convergence rates.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


def estimate_pass_at_k(num_samples: int, num_correct: int, k: int = 1) -> float:
    """
    Estimates unbiased Pass@k metric using standard combinatorial formula:
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
    tokens_generated: int = 0
    tokens_per_sec: float = 0.0
    error_detail: Optional[str] = None


@dataclass
class BenchmarkSummary:
    benchmark_name: str
    total_tasks: int
    passed_tasks: int
    pass_at_1: float  # Percentage (e.g. 85.5)
    pass_at_5: float = 0.0
    avg_latency_sec: float = 0.0
    avg_tokens_per_sec: float = 0.0
    convergence_rate: float = 0.0  # Percentage of tasks solved within attempts
    task_results: List[HarnessTaskResult] = field(default_factory=list)


def compute_benchmark_summary(benchmark_name: str, results: List[HarnessTaskResult]) -> BenchmarkSummary:
    """Aggregates raw task execution results into standard statistical benchmark metrics."""
    if not results:
        return BenchmarkSummary(
            benchmark_name=benchmark_name,
            total_tasks=0,
            passed_tasks=0,
            pass_at_1=0.0
        )

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    total_latency = sum(r.latency_sec for r in results)
    total_tokens = sum(r.tokens_generated for r in results)
    total_tok_sec = sum(r.tokens_per_sec for r in results)

    pass_1 = round((passed / total) * 100, 2)
    avg_latency = round(total_latency / total, 2)
    avg_tok_sec = round(total_tok_sec / total, 1) if total > 0 else 0.0
    conv_rate = round((sum(1 for r in results if r.passed and r.attempts_used <= 2) / total) * 100, 1)

    return BenchmarkSummary(
        benchmark_name=benchmark_name,
        total_tasks=total,
        passed_tasks=passed,
        pass_at_1=pass_1,
        pass_at_5=round(estimate_pass_at_k(total, passed, k=min(5, total)) * 100, 2),
        avg_latency_sec=avg_latency,
        avg_tokens_per_sec=avg_tok_sec,
        convergence_rate=conv_rate,
        task_results=results
    )

