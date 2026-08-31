"""Tests for Smart Surgical Diff Preview Engine and Change Impact Analyzer."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.diff_engine import DiffEngine, DiffResult
from saleha.core.change_impact import ChangeImpactAnalyzer, ImpactReport


OLD_CODE = '''def greet(name):
    return "Hello " + name


def add(a, b):
    return a + b
'''

NEW_CODE = '''def greet(name: str) -> str:
    """Return greeting string."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Return sum."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Return product."""
    return a * b
'''


class DiffEngineTests(unittest.TestCase):

    def setUp(self):
        self.engine = DiffEngine()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_compute_diff_basic(self):
        diff = self.engine.compute_diff("utils.py", OLD_CODE, NEW_CODE)
        self.assertEqual(diff.file_path, "utils.py")
        self.assertGreater(diff.lines_added, 0)
        self.assertGreater(diff.lines_removed, 0)
        self.assertIsInstance(diff.unified_diff, str)
        self.assertIn("+", diff.unified_diff)

    def test_risk_score_range(self):
        diff = self.engine.compute_diff("utils.py", OLD_CODE, NEW_CODE)
        self.assertGreaterEqual(diff.risk_score, 1)
        self.assertLessEqual(diff.risk_score, 10)

    def test_no_change_diff(self):
        diff = self.engine.compute_diff("same.py", OLD_CODE, OLD_CODE)
        self.assertEqual(diff.lines_added, 0)
        self.assertEqual(diff.lines_removed, 0)
        self.assertEqual(len(diff.hunks), 0)

    def test_critical_file_higher_risk(self):
        diff_normal = self.engine.compute_diff("utils.py", OLD_CODE, NEW_CODE)
        diff_critical = self.engine.compute_diff("commands.py", OLD_CODE, NEW_CODE)
        self.assertGreaterEqual(diff_critical.risk_score, diff_normal.risk_score)

    def test_dangerous_pattern_increases_risk(self):
        dangerous_new = OLD_CODE + "\nimport subprocess\nsubprocess.run(['rm', '-rf', '/'])"
        diff = self.engine.compute_diff("script.py", OLD_CODE, dangerous_new)
        self.assertGreater(diff.risk_score, 2)

    def test_hunks_parsed(self):
        diff = self.engine.compute_diff("f.py", OLD_CODE, NEW_CODE)
        self.assertIsInstance(diff.hunks, list)
        if diff.hunks:
            hunk = diff.hunks[0]
            self.assertIsInstance(hunk.hunk_id, int)
            self.assertIsInstance(hunk.lines_added, int)

    def test_apply_and_rollback(self):
        fpath = os.path.join(self.tmp, "target.py")
        with open(fpath, "w") as f:
            f.write(OLD_CODE)
        ok, msg = self.engine.apply_diff(fpath, NEW_CODE, backup=True)
        self.assertTrue(ok, msg)
        with open(fpath) as f:
            self.assertEqual(f.read(), NEW_CODE)
        ok2, msg2 = self.engine.rollback(fpath)
        self.assertTrue(ok2, msg2)
        with open(fpath) as f:
            self.assertEqual(f.read(), OLD_CODE)

    def test_apply_nonexistent_file(self):
        ok, msg = self.engine.apply_diff("/nonexistent/path.py", "code", backup=False)
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_rollback_no_backup(self):
        fpath = os.path.join(self.tmp, "no_backup.py")
        with open(fpath, "w") as f:
            f.write(OLD_CODE)
        ok, msg = self.engine.rollback(fpath)
        self.assertFalse(ok)

    def test_format_rich_preview(self):
        diff = self.engine.compute_diff("utils.py", OLD_CODE, NEW_CODE)
        preview = self.engine.format_rich_preview(diff)
        self.assertIn("utils.py", preview)
        self.assertIn("Risk", preview)

    def test_is_safe_property(self):
        diff = self.engine.compute_diff("small.py", "x = 1", "x = 2")
        self.assertIsInstance(diff.is_safe, bool)

    def test_change_summary(self):
        diff = self.engine.compute_diff("f.py", OLD_CODE, NEW_CODE)
        summary = diff.change_summary
        self.assertIn("+", summary)
        self.assertIn("-", summary)


class ChangeImpactTests(unittest.TestCase):

    def setUp(self):
        self.analyzer = ChangeImpactAnalyzer()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_changed_symbols(self):
        report = self.analyzer.analyze(OLD_CODE, NEW_CODE, "utils.py", self.tmp)
        self.assertIsInstance(report.changed_symbols, list)
        self.assertIn("greet", report.changed_symbols)

    def test_detects_new_symbol(self):
        report = self.analyzer.analyze(OLD_CODE, NEW_CODE, "utils.py", self.tmp)
        self.assertIn("multiply", report.changed_symbols)

    def test_blast_radius_range(self):
        report = self.analyzer.analyze(OLD_CODE, NEW_CODE, "utils.py", self.tmp)
        self.assertGreaterEqual(report.blast_radius, 0)
        self.assertLessEqual(report.blast_radius, 100)

    def test_risk_levels(self):
        report = self.analyzer.analyze(OLD_CODE, NEW_CODE, "utils.py", self.tmp)
        self.assertIn(report.risk_level, ["low", "medium", "high", "critical"])

    def test_summary_is_string(self):
        report = self.analyzer.analyze(OLD_CODE, NEW_CODE, "utils.py", self.tmp)
        self.assertIsInstance(report.summary, str)
        self.assertGreater(len(report.summary), 10)

    def test_no_change_low_radius(self):
        report = self.analyzer.analyze(OLD_CODE, OLD_CODE, "f.py", self.tmp)
        self.assertEqual(len(report.changed_symbols), 0)


if __name__ == "__main__":
    unittest.main()

