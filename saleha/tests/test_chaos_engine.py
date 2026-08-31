"""Unit tests for Autonomous Chaos Engineering Engine."""

from __future__ import annotations

import unittest
from saleha.core.chaos_engine import ChaosEngine, ChaosFaultConfig, ChaosProbeResult


class ChaosEngineTests(unittest.TestCase):

    def setUp(self):
        self.engine = ChaosEngine()

    def test_wrap_execution_injects_latency_and_exceptions(self):
        def sample_func(val):
            return val * 2

        # 1. Successful execution without faults
        res = self.engine.wrap_execution(sample_func, 10, config=ChaosFaultConfig())
        self.assertEqual(res, 20)

        # 2. Timeout fault injection
        with self.assertRaises(TimeoutError):
            self.engine.wrap_execution(sample_func, 10, config=ChaosFaultConfig(simulate_timeout=True))

        # 3. Guaranteed exception injection
        with self.assertRaises(RuntimeError):
            self.engine.wrap_execution(sample_func, 10, config=ChaosFaultConfig(failure_rate=1.0))

    def test_probe_resilience_scoring(self):
        def resilient_callable():
            return "ok"

        probe = self.engine.probe_resilience(resilient_callable, iterations=10, config=ChaosFaultConfig(failure_rate=0.5))
        self.assertEqual(probe.total_iterations, 10)
        self.assertGreaterEqual(probe.resilience_score, 0.0)


if __name__ == "__main__":
    unittest.main()

