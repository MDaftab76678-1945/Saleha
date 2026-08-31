"""Unit tests for RepoWatcher incremental AST engine."""

import os
import time
import tempfile
import unittest

from saleha.core.repo_watcher import RepoWatcher, RepoChangeEvent


class RepoWatcherTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.file_a = os.path.join(self.root, "module_a.py")
        with open(self.file_a, "w") as f:
            f.write("def calculate_price(amount):\n    return amount * 1.18\n")

        self.watcher = RepoWatcher(root_dir=self.root, poll_interval=0.1, debounce_sec=0.05)
        self.watcher.initialize()

    def tearDown(self):
        self.watcher.stop()
        self._tmp.cleanup()

    def test_detects_file_modification(self):
        events = []
        self.watcher.on_change(events.append)

        # Sleep slightly to ensure timestamp increment
        time.sleep(0.1)
        with open(self.file_a, "a") as f:
            f.write("\ndef discount(amount):\n    return amount * 0.9\n")

        detected = self.watcher.poll_once()
        self.assertGreaterEqual(len(detected), 1)
        self.assertEqual(detected[0].change_type, "modified")
        self.assertIn("discount", detected[0].symbols_defined)

    def test_detects_file_creation(self):
        events = []
        self.watcher.on_change(events.append)

        time.sleep(0.1)
        file_b = os.path.join(self.root, "module_b.py")
        with open(file_b, "w") as f:
            f.write("from module_a import calculate_price\ndef checkout():\n    return calculate_price(100)\n")

        detected = self.watcher.poll_once()
        self.assertGreaterEqual(len(detected), 1)
        self.assertEqual(detected[0].change_type, "created")

    def test_background_thread_start_and_stop(self):
        self.watcher.start_background()
        self.assertTrue(self.watcher.is_running)
        self.watcher.stop()
        self.assertFalse(self.watcher.is_running)


if __name__ == "__main__":
    unittest.main()

