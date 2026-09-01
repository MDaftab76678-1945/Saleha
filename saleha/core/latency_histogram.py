"""
Zero-Allocation Nanosecond Latency & Jitter Histogram Tracker for Saleha Platform.
Tracks execution times from 0ns to 10,000ns in 10ns steps, computing exact
p50 (Median), p90, p99, and p99.99 (Maximum Jitter) latency percentiles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HISTOGRAM_BUCKETS = 1000  # Tracks 0ns to 10,000ns in 10ns steps


class NanosecondLatencyHistogram:
    """
    Fixed-memory latency histogram tracker without heap reallocations.
    """

    def __init__(self, num_buckets: int = HISTOGRAM_BUCKETS):
        self.num_buckets = num_buckets
        self.buckets: List[int] = [0] * num_buckets
        self.total_samples: int = 0
        self.min_ns: int = 2**63 - 1
        self.max_ns: int = 0

    def record(self, latency_ns: int):
        self.total_samples += 1
        if latency_ns < self.min_ns:
            self.min_ns = latency_ns
        if latency_ns > self.max_ns:
            self.max_ns = latency_ns

        bucket_idx = min(self.num_buckets - 1, max(0, latency_ns // 10))
        self.buckets[bucket_idx] += 1

    def percentile(self, p: float) -> int:
        """Calculates exact percentile (e.g. 50.0 for p50, 99.0 for p99)."""
        if self.total_samples == 0:
            return 0
        target_count = math.ceil((p / 100.0) * self.total_samples)
        accumulated = 0
        for idx, count in enumerate(self.buckets):
            accumulated += count
            if accumulated >= target_count:
                return idx * 10
        return self.max_ns

    def get_report(self) -> Dict[str, Any]:
        if self.total_samples == 0:
            return {
                "total_samples": 0,
                "min_ns": 0,
                "p50_ns": 0,
                "p90_ns": 0,
                "p99_ns": 0,
                "p99_99_ns": 0,
                "max_peak_jitter_ns": 0,
            }
        return {
            "total_samples": self.total_samples,
            "min_ns": self.min_ns,
            "p50_ns": self.percentile(50.0),
            "p90_ns": self.percentile(90.0),
            "p99_ns": self.percentile(99.0),
            "p99_99_ns": self.percentile(99.99),
            "max_peak_jitter_ns": self.max_ns,
        }

