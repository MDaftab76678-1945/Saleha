"""Unit tests for saleha.core.stats_tracker.StatsTracker. Had no test
coverage before this file (found during a test-coverage sweep of
saleha/core/)."""

import json
import os
import tempfile
import unittest

from saleha.core.stats_tracker import StatsTracker, ModelStats


class StatsTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp_dir, "stats.json")

    def test_no_stats_yet_returns_zeroed_model_stats(self) -> None:
        tracker = StatsTracker(path=self.path)
        stats = tracker.get_model_stats("qwen3.5:4b")
        self.assertEqual(stats.uses, 0)
        self.assertEqual(stats.success_rate, 0.0)

    def test_record_persists_to_disk_and_reloads(self) -> None:
        tracker = StatsTracker(path=self.path)
        tracker.record(model="qwen3.5:4b", success=True, attempts=1, task_type="coding")
        tracker.record(model="qwen3.5:4b", success=True, attempts=1, task_type="coding")
        tracker.record(model="qwen3.5:4b", success=False, attempts=3, task_type="coding")

        # A fresh instance reading the same file must see the same data --
        # this is the exact persistence gap the module's docstring says it
        # fixes ("Restart Saleha and it's gone").
        reloaded = StatsTracker(path=self.path)
        stats = reloaded.get_model_stats("qwen3.5:4b", task_type="coding")
        self.assertEqual(stats.uses, 3)
        self.assertEqual(stats.successes, 2)
        self.assertAlmostEqual(stats.success_rate, 66.7, places=1)

    def test_task_types_are_tracked_independently(self) -> None:
        tracker = StatsTracker(path=self.path)
        tracker.record(model="m1", success=True, task_type="coding")
        tracker.record(model="m1", success=False, task_type="chat")

        coding_stats = tracker.get_model_stats("m1", task_type="coding")
        chat_stats = tracker.get_model_stats("m1", task_type="chat")
        self.assertEqual(coding_stats.uses, 1)
        self.assertTrue(coding_stats.successes == 1)
        self.assertEqual(chat_stats.uses, 1)
        self.assertEqual(chat_stats.successes, 0)

    def test_best_model_for_requires_minimum_uses(self) -> None:
        tracker = StatsTracker(path=self.path)
        # One use, 100% success -- a flukey single data point, must not win.
        tracker.record(model="lucky_once", success=True, task_type="coding")
        # Two uses, 50% success -- meets the min_uses=2 default.
        tracker.record(model="steady", success=True, task_type="coding")
        tracker.record(model="steady", success=False, task_type="coding")

        best = tracker.best_model_for(task_type="coding")
        self.assertEqual(best, "steady")

    def test_best_model_for_returns_none_when_nothing_meets_threshold(self) -> None:
        tracker = StatsTracker(path=self.path)
        tracker.record(model="m1", success=True, task_type="coding")
        self.assertIsNone(tracker.best_model_for(task_type="coding", min_uses=2))

    def test_corrupt_stats_file_is_backed_up_and_starts_fresh(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        tracker = StatsTracker(path=self.path)
        self.assertEqual(tracker.get_model_stats("anything").uses, 0)

        backup_path = self.path + ".corrupt"
        self.assertTrue(os.path.exists(backup_path))
        with open(backup_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "{not valid json")

    def test_summary_reports_no_stats_message_when_empty(self) -> None:
        tracker = StatsTracker(path=self.path)
        summary = tracker.summary(task_type="coding")
        self.assertIn("No stats yet", summary)

    def test_summary_lists_recorded_models(self) -> None:
        tracker = StatsTracker(path=self.path)
        tracker.record(model="qwen3.5:4b", success=True, task_type="coding")
        summary = tracker.summary(task_type="coding")
        self.assertIn("qwen3.5:4b", summary)
        self.assertIn("1 uses", summary)


if __name__ == "__main__":
    unittest.main()
