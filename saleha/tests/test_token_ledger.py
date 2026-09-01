"""Unit tests for Double-Entry Token Economics & ROI Ledger."""

import unittest
import tempfile
import os
from saleha.core.token_ledger import TokenLedger, LedgerEntry


class TestTokenLedger(unittest.TestCase):
    """Test suite for TokenLedger double-entry transactions and ROI metrics."""

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        self.ledger = TokenLedger(store_path=self.tmp_file)

    def tearDown(self):
        if os.path.exists(self.tmp_file):
            try:
                os.unlink(self.tmp_file)
            except OSError:
                pass

    def test_record_transaction_and_summary(self):
        entry = self.ledger.record_transaction(
            task_id="task_101",
            model="qwen2.5-coder:1.5b",
            prompt_tokens=400,
            completion_tokens=200,
            saved_tokens=800,
            duration_sec=1.2,
            note="Cached hit",
        )
        self.assertIsInstance(entry, LedgerEntry)
        self.assertEqual(entry.task_id, "task_101")

        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_transactions"], 1)
        self.assertEqual(summary["total_tokens_consumed"], 600)
        self.assertEqual(summary["total_tokens_saved"], 800)
        self.assertGreater(summary["token_roi_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
