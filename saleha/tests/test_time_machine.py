"""Unit tests for Codebase Snapshot & Time-Machine Rollback."""

import unittest
import tempfile
import os
from saleha.core.time_machine import TimeMachine, CodebaseSnapshot


class TestTimeMachine(unittest.TestCase):
    """Test suite for TimeMachine atomic snapshot and rollback."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmp_dir, "app.py")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("VERSION = 1\n")
        self.tm = TimeMachine()

    def tearDown(self):
        import shutil
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


if __name__ == "__main__":
    unittest.main()
