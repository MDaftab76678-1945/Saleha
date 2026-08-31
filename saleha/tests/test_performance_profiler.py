"""Unit tests for Continuous Performance & Memory Profiler."""

from __future__ import annotations

import unittest
from saleha.core.performance_profiler import PerformanceProfiler, ProfileMetrics


class PerformanceProfilerTests(unittest.TestCase):

    def setUp(self):
        self.profiler = PerformanceProfiler()

    def test_profile_callable_measures_metrics(self):
        def sample_workload():
            data = [i ** 2 for i in range(1000)]
            return len(data)

        ret, metrics = self.profiler.profile_callable(sample_workload)
        self.assertEqual(ret, 1000)
        self.assertTrue(metrics.success)
        self.assertGreaterEqual(metrics.duration_ms, 0.0)
        self.assertGreaterEqual(metrics.peak_memory_mb, 0.0)


if __name__ == "__main__":
    unittest.main()
