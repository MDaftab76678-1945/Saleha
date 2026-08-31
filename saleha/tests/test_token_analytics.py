"""Unit tests for Token Economics & Cloud Cost Analytics Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.token_analytics import TokenAnalyticsEngine, InvocationRecord


class TokenAnalyticsTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "test_analytics.json")
        self.analytics = TokenAnalyticsEngine(storage_path=self.storage_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_invocation_calculates_savings_and_speed(self):
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

    def test_disk_persistence_and_reload(self):
        self.analytics.record_invocation(prompt_tokens=500, completion_tokens=200, response_time_sec=2.0)
        self.assertTrue(os.path.isfile(self.storage_path))

        # Reload in new instance
        new_engine = TokenAnalyticsEngine(storage_path=self.storage_path)
        self.assertEqual(new_engine.total_invocations, 1)
        self.assertEqual(new_engine.total_prompt_tokens, 500)


if __name__ == "__main__":
    unittest.main()

