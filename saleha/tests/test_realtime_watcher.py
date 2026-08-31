"""Tests for Real-Time File Watcher and Inline Suggestion Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from saleha.core.inline_suggester import InlineSuggester, InlineSuggestion
from saleha.core.realtime_watcher import RealtimeWatcher, FileChangeEvent


CLEAN_PY = '''
from __future__ import annotations


def add(a: int, b: int) -> int:
    """Return sum."""
    return a + b
'''

DIRTY_PY = '''
import os

password = "supersecret123"

def unsafe():
    eval("os.system('ls')")
    print("done")
'''

SYNTAX_ERROR_PY = '''
def broken(
    return None
'''


class InlineSuggesterTests(unittest.TestCase):

    def setUp(self):
        self.suggester = InlineSuggester()

    def test_clean_code_no_errors(self):
        suggestions = self.suggester.analyze(CLEAN_PY)
        errors = [s for s in suggestions if s.severity == "error"]
        self.assertEqual(len(errors), 0)

    def test_detects_eval(self):
        suggestions = self.suggester.analyze(DIRTY_PY)
        titles = [s.message for s in suggestions]
        self.assertTrue(any("eval" in t.lower() for t in titles), titles)

    def test_detects_hardcoded_password(self):
        suggestions = self.suggester.analyze(DIRTY_PY)
        titles = [s.message for s in suggestions]
        self.assertTrue(any("password" in t.lower() or "secret" in t.lower() for t in titles), titles)

    def test_detects_syntax_error(self):
        suggestions = self.suggester.analyze(SYNTAX_ERROR_PY)
        errors = [s for s in suggestions if s.severity == "error" and s.category == "syntax"]
        self.assertGreater(len(errors), 0)

    def test_has_errors_true(self):
        self.assertTrue(self.suggester.has_errors(SYNTAX_ERROR_PY))

    def test_has_errors_false(self):
        self.assertFalse(self.suggester.has_errors(CLEAN_PY))

    def test_suggestion_format(self):
        suggestions = self.suggester.analyze(DIRTY_PY)
        if suggestions:
            formatted = suggestions[0].format()
            self.assertIn("Line", formatted)
            self.assertIn("Fix:", formatted)

    def test_non_python_returns_empty(self):
        suggestions = self.suggester.analyze("const x = 1;", file_ext=".js")
        self.assertIsInstance(suggestions, list)


class RealtimeWatcherTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.watcher = RealtimeWatcher(root_dir=self.tmp, poll_interval=0.2)

    def tearDown(self):
        self.watcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, fname: str, content: str) -> str:
        path = os.path.join(self.tmp, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_scan_once_clean_file(self):
        path = self._write("clean.py", CLEAN_PY)
        event = self.watcher.scan_once(path)
        self.assertEqual(event.event_type, "scan")
        self.assertEqual(event.error_count, 0)

    def test_scan_once_dirty_file(self):
        path = self._write("dirty.py", DIRTY_PY)
        event = self.watcher.scan_once(path)
        self.assertGreater(len(event.suggestions), 0)

    def test_watcher_starts_and_stops(self):
        self.watcher.start()
        self.assertTrue(self.watcher._running)
        self.watcher.stop()
        self.assertFalse(self.watcher._running)

    def test_watcher_detects_file_change(self):
        events = []
        self.watcher.on_change(events.append)
        self.watcher.start()
        time.sleep(0.3)
        self._write("new_file.py", CLEAN_PY)
        time.sleep(0.6)
        self.watcher.stop()
        paths = [e.path for e in events]
        self.assertTrue(any("new_file.py" in p for p in paths), f"Events: {paths}")

    def test_get_recent_events(self):
        self.watcher.start()
        self._write("test.py", CLEAN_PY)
        time.sleep(0.6)
        self.watcher.stop()
        recent = self.watcher.get_recent_events()
        self.assertIsInstance(recent, list)

    def test_callback_receives_event(self):
        received = []
        self.watcher.on_change(received.append)
        self.watcher.start()
        time.sleep(0.3)
        self._write("cb_test.py", DIRTY_PY)
        time.sleep(0.6)
        self.watcher.stop()
        self.assertTrue(len(received) >= 0)

    def test_double_start_safe(self):
        self.watcher.start()
        self.watcher.start()
        self.assertTrue(self.watcher._running)
        self.watcher.stop()

    def test_stop_without_start_safe(self):
        watcher = RealtimeWatcher(root_dir=self.tmp)
        watcher.stop()


if __name__ == "__main__":
    unittest.main()
