"""Unit tests for Token Economics & Cloud Cost Analytics Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.token_analytics import TokenAnalyticsEngine, InvocationRecord


class TokenAnalyticsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "test_analytics.json")
        self.analytics = TokenAnalyticsEngine(storage_path=self.storage_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_invocation_calculates_savings_and_speed(self) -> None:
        rec = self.analytics.record_invocation(
            prompt_tokens=1000,
            completion_tokens=500,
            response_time_sec=10.0,
            model="qwen2.5-coder:7b",
            reasoning_tokens=150
        )
        self.assertEqual(rec.total_tokens, 1500)
        self.assertEqual(rec.tokens_per_sec, 50.0)
        self.assertGreater(rec.cost_saved_usd, 0.0)

        # Check cumulative summary
        summary = self.analytics.get_summary()
        self.assertEqual(summary["total_invocations"], 1)
        self.assertEqual(summary["total_tokens"], 1500)
        self.assertIn("USD", summary["claude_equivalent_saved"])

    def test_zero_token_handling_accuracy(self) -> None:
        rec = self.analytics.record_invocation(
            prompt_tokens=0,
            completion_tokens=0,
            response_time_sec=1.0,
            model="local-test",
        )
        self.assertEqual(rec.prompt_tokens, 0)
        self.assertEqual(rec.completion_tokens, 0)
        self.assertEqual(rec.total_tokens, 0)
        self.assertEqual(rec.tokens_per_sec, 0.0)

    def test_latency_percentiles_calculation(self) -> None:
        # Empty percentiles
        empty_pct = self.analytics.get_latency_percentiles()
        self.assertEqual(empty_pct["p50"], 0.0)

        # Invocations with varying speeds: 10 tps, 20 tps, 30 tps, 40 tps, 50 tps
        for tokens, sec in [(100, 10.0), (200, 10.0), (300, 10.0), (400, 10.0), (500, 10.0)]:
            self.analytics.record_invocation(prompt_tokens=50, completion_tokens=tokens, response_time_sec=sec)

        pcts = self.analytics.get_latency_percentiles()
        self.assertEqual(pcts["sample_count"], 5.0)
        self.assertEqual(pcts["p50"], 30.0)
        self.assertGreaterEqual(pcts["p90"], 40.0)
        self.assertEqual(pcts["p95"], 50.0)

    def test_clear_resets_analytics(self) -> None:
        self.analytics.record_invocation(prompt_tokens=500, completion_tokens=200, response_time_sec=2.0)
        self.assertEqual(self.analytics.total_invocations, 1)

        self.analytics.clear()
        self.assertEqual(self.analytics.total_invocations, 0)
        self.assertEqual(self.analytics.total_prompt_tokens, 0)
        self.assertEqual(self.analytics.total_completion_tokens, 0)
        self.assertEqual(len(self.analytics.records), 0)

        summary = self.analytics.get_summary()
        self.assertEqual(summary["total_invocations"], 0)
        self.assertEqual(summary["total_tokens"], 0)

    def test_disk_persistence_and_reload(self) -> None:
        self.analytics.record_invocation(prompt_tokens=500, completion_tokens=200, response_time_sec=2.0)
        self.assertTrue(os.path.isfile(self.storage_path))

        # Reload in new instance
        new_engine = TokenAnalyticsEngine(storage_path=self.storage_path)
        self.assertEqual(new_engine.total_invocations, 1)
        self.assertEqual(new_engine.total_prompt_tokens, 500)


if __name__ == "__main__":
    unittest.main()


