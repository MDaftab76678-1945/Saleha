import tempfile
import unittest
from pathlib import Path

from saleha.core.task_history import TaskHistory


class TaskHistoryTests(unittest.TestCase):
    def test_recent_zero_or_negative_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = TaskHistory(str(Path(tmp) / "history.jsonl"))
            history.log("first", "test-model", True, 1)
            history.log("second", "test-model", True, 1)

            self.assertEqual(history.recent(0), [])
            self.assertEqual(history.recent(-1), [])

    def test_recent_returns_requested_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = TaskHistory(str(Path(tmp) / "history.jsonl"))
            history.log("first", "test-model", True, 1)
            history.log("second", "test-model", True, 1)

            records = history.recent(1)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].goal, "second")


if __name__ == "__main__":
    unittest.main()
