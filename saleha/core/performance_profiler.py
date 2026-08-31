"""
Saleha Core: Continuous Performance & Memory Profiler

Measures execution duration, peak RAM allocations, memory leaks, and CPU overhead
for functions, scripts, and agent pipelines.
"""

from __future__ import annotations

import time
import tracemalloc
import gc
from dataclasses import dataclass
from typing import Callable, Any, Dict, Optional, Tuple


@dataclass
class ProfileMetrics:
    duration_ms: float
    peak_memory_mb: float
    current_memory_mb: float
    gc_collections: int
    success: bool = True
    error: str = ""


class PerformanceProfiler:
    """Profiles memory footprint and execution latency of arbitrary code."""

    def profile_callable(self, func: Callable, *args, **kwargs) -> Tuple[Any, ProfileMetrics]:
        """Profiles a Python callable for latency and memory allocations."""
        gc.collect()
        gc_before = gc.get_count()
        tracemalloc.start()
        start_t = time.perf_counter()

        ret = None
        err = ""
        success = True

        try:
            ret = func(*args, **kwargs)
        except Exception as e:
            success = False
            err = str(e)

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        gc_after = gc.get_count()
        gc_diff = sum(abs(a - b) for a, b in zip(gc_after, gc_before))

        metrics = ProfileMetrics(
            duration_ms=round(elapsed_ms, 2),
            peak_memory_mb=round(peak / (1024 * 1024), 3),
            current_memory_mb=round(current / (1024 * 1024), 3),
            gc_collections=gc_diff,
            success=success,
            error=err
        )

        return ret, metrics


# Global instance
performance_profiler = PerformanceProfiler()
