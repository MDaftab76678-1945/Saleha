"""Unit tests for Double-Entry Token Economics & ROI Ledger."""

from __future__ import annotations

import os
import tempfile
import unittest
from saleha.core.telemetry.token_ledger import TokenLedger, LedgerEntry


class TestTokenLedger(unittest.TestCase):
    """Test suite for TokenLedger double-entry transactions and ROI metrics."""

    def setUp(self) -> None:
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        self.ledger = TokenLedger(store_path=self.tmp_file)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_file):
            try:
                os.unlink(self.tmp_file)
            except OSError:
                pass

    def test_record_transaction_and_summary(self) -> None:
        entry = self.ledger.record_transaction(
            task_id="task_101",
            model="qwen2.5-coder:3b",
            prompt_tokens=400,
            completion_tokens=200,
            saved_tokens=800,
            duration_sec=1.2,
            note="Cached hit",
        )
        self.assertIsInstance(entry, LedgerEntry)
        self.assertEqual(entry.task_id, "task_101")
        self.assertTrue(entry.entry_id.startswith("tx_1_"))

        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_transactions"], 1)
        self.assertEqual(summary["total_tokens_consumed"], 600)
        self.assertEqual(summary["total_tokens_saved"], 800)
        self.assertGreater(summary["token_roi_percent"], 100.0)

    def test_filter_by_model_and_task(self) -> None:
        self.ledger.record_transaction("task_a", "qwen2.5-coder:3b", 100, 50)
        self.ledger.record_transaction("task_b", "deepseek-coder:6.7b", 200, 100)
        self.ledger.record_transaction("task_a", "qwen2.5-coder:3b", 300, 150)

        qwen_entries = self.ledger.filter_by_model("qwen2.5-coder:3b")
        self.assertEqual(len(qwen_entries), 2)

        deepseek_entries = self.ledger.filter_by_model("deepseek-coder:6.7b")
        self.assertEqual(len(deepseek_entries), 1)

        task_a_entries = self.ledger.filter_by_task("task_a")
        self.assertEqual(len(task_a_entries), 2)

    def test_clear(self) -> None:
        self.ledger.record_transaction("task_1", "model_a", 100, 50)
        self.assertEqual(len(self.ledger.entries), 1)

        self.ledger.clear()
        self.assertEqual(len(self.ledger.entries), 0)

        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_transactions"], 0)
        self.assertEqual(summary["total_tokens_consumed"], 0)

    def test_export_and_import_json(self) -> None:
        self.ledger.record_transaction("task_exp_1", "model_x", 150, 75, saved_tokens=500)
        export_path = f"{self.tmp_file}.export.json"
        try:
            self.assertTrue(self.ledger.export_json(export_path))
            self.assertTrue(os.path.isfile(export_path))

            # Fresh ledger
            fresh_file = f"{self.tmp_file}.fresh.json"
            fresh_ledger = TokenLedger(store_path=fresh_file)
            self.assertEqual(len(fresh_ledger.entries), 0)

            imported_count = fresh_ledger.import_json(export_path)
            self.assertEqual(imported_count, 1)
            self.assertEqual(len(fresh_ledger.entries), 1)
            self.assertEqual(fresh_ledger.entries[0].task_id, "task_exp_1")

            # Clean up fresh_file
            if os.path.exists(fresh_file):
                os.unlink(fresh_file)
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_atomic_disk_persistence_and_reload(self) -> None:
        self.ledger.record_transaction("task_persist", "qwen3:8b", 500, 250)
        self.assertTrue(os.path.isfile(self.tmp_file))

        # Reload in a new instance
        reloaded = TokenLedger(store_path=self.tmp_file)
        self.assertEqual(len(reloaded.entries), 1)
        self.assertEqual(reloaded.entries[0].task_id, "task_persist")


if __name__ == "__main__":
    unittest.main()
