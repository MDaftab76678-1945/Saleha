"""Unit tests for Codebase Snapshot & Time-Machine Rollback."""

import unittest
import tempfile
import os
import shutil
from saleha.core.time_machine import TimeMachine, CodebaseSnapshot


class TestTimeMachine(unittest.TestCase):
    """Test suite for TimeMachine atomic snapshot and rollback."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.store_dir = os.path.join(self.tmp_dir, "store")
        self.test_file = os.path.join(self.tmp_dir, "app.py")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("VERSION = 1\n")
        self.tm = TimeMachine(store_dir=self.store_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_snapshot_and_rollback(self):
        snap = self.tm.create_snapshot([self.test_file], label="initial_v1")
        self.assertIsInstance(snap, CodebaseSnapshot)
        self.assertEqual(snap.file_count, 1)

        # Mutate file (corrupt or refactor)
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("VERSION = 2_CORRUPTED\n")

        # Rollback
        success, msg = self.tm.rollback(snap.snapshot_id)
        self.assertTrue(success)

        # Verify content restored
        with open(self.test_file, "r", encoding="utf-8") as f:
            restored_content = f.read()
        self.assertEqual(restored_content, "VERSION = 1\n")

    def test_snapshot_persists_across_instances(self):
        """A snapshot taken by one instance must be visible to another.

        This is the failure the disk-persistence fix addresses: the old
        in-memory-only TimeMachine returned "No snapshots available" whenever
        `saleha snapshot` and `saleha rollback` ran in different processes.
        """
        snap = self.tm.create_snapshot([self.test_file], label="cross_proc")

        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("VERSION = broken\n")

        # A completely separate instance, as a second `saleha` process would be.
        other = TimeMachine(store_dir=self.store_dir)
        self.assertEqual(len(other.list_snapshots()), 1)
        self.assertEqual(other.list_snapshots()[0]["snapshot_id"], snap.snapshot_id)

        success, _ = other.rollback()  # latest, no id
        self.assertTrue(success)
        with open(self.test_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "VERSION = 1\n")

    def test_rollback_with_no_snapshots(self):
        empty = TimeMachine(store_dir=os.path.join(self.tmp_dir, "nonexistent"))
        success, msg = empty.rollback()
        self.assertFalse(success)
        self.assertIn("No snapshots available", msg)

    def test_prune_keeps_only_max_snapshots(self):
        tm = TimeMachine(max_snapshots=3, store_dir=self.store_dir)
        for i in range(5):
            with open(self.test_file, "w", encoding="utf-8") as f:
                f.write(f"VERSION = {i}\n")
            tm.create_snapshot([self.test_file], label=f"v{i}")

        listed = tm.list_snapshots()
        self.assertEqual(len(listed), 3)
        # The three kept are the newest three, in timestamp order.
        self.assertEqual([s["label"] for s in listed], ["v2", "v3", "v4"])

    def test_corrupt_snapshot_file_is_skipped(self):
        good = self.tm.create_snapshot([self.test_file], label="good")
        os.makedirs(self.store_dir, exist_ok=True)
        with open(os.path.join(self.store_dir, "snap_bad.json"), "w", encoding="utf-8") as f:
            f.write("{ not valid json")

        listed = self.tm.list_snapshots()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["snapshot_id"], good.snapshot_id)


if __name__ == "__main__":
    unittest.main()
