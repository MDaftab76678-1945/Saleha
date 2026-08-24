"""
Saleha Harness: Industrial-Strength Multi-Domain Model Evaluation Framework
"""

from saleha.harness.core import SalehaHarness, harness
from saleha.harness.benchmarks import BenchmarkCatalog, BenchmarkTaskSpec
from saleha.harness.metrics import (
    estimate_pass_at_k,
    HarnessTaskResult,
    BenchmarkSummary,
    compute_benchmark_summary
)
from saleha.harness.reporter import HarnessReport, HarnessReporter, reporter

__all__ = [
    "SalehaHarness",
    "harness",
    "BenchmarkCatalog",
    "BenchmarkTaskSpec",
    "estimate_pass_at_k",
    "HarnessTaskResult",
    "BenchmarkSummary",
    "compute_benchmark_summary",
    "HarnessReport",
    "HarnessReporter",
    "reporter"
]

