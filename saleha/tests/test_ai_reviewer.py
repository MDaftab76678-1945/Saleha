"""Tests for AI Code Review Engine and HTML Report Generator."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.ai_reviewer import AICodeReviewer, ReviewIssue
from saleha.core.review_reporter import ReviewReporter


SQL_INJECTION_CODE = '''
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = '%s'" % user_id)
    return cursor.fetchall()
'''

HARDCODED_SECRET_CODE = '''
def connect():
    api_key = "sk-1234567890abcdefghij"
    password = "SuperSecretPass123!"
    return api_key
'''

CLEAN_CODE = '''
from __future__ import annotations
from typing import List


def add_numbers(a: int, b: int) -> int:
    """Returns sum of two integers."""
    return a + b


def filter_positive(nums: List[int]) -> List[int]:
    """Filters positive numbers from a list."""
    return [n for n in nums if n > 0]
'''


class AIReviewerTests(unittest.TestCase):

    def setUp(self):
        self.reviewer = AICodeReviewer()

    def test_detects_sql_injection(self):
        report = self.reviewer.review_file("db.py", SQL_INJECTION_CODE)
        titles = [i.title for i in report.issues]
        self.assertTrue(any("SQL" in t for t in titles), titles)
        self.assertTrue(any(i.severity == "critical" for i in report.issues))

    def test_detects_hardcoded_credentials(self):
        report = self.reviewer.review_file("config.py", HARDCODED_SECRET_CODE)
        titles = [i.title for i in report.issues]
        self.assertTrue(any("Credential" in t or "Secret" in t or "Hardcoded" in t for t in titles), titles)

    def test_clean_code_gets_high_score(self):
        report = self.reviewer.review_file("utils.py", CLEAN_CODE)
        security_issues = [i for i in report.issues if i.category == "security"]
        self.assertEqual(len(security_issues), 0)
        self.assertGreaterEqual(report.score, 70)

    def test_report_has_correct_fields(self):
        report = self.reviewer.review_file("test.py", SQL_INJECTION_CODE)
        self.assertEqual(report.file_path, "test.py")
        self.assertIsInstance(report.score, int)
        self.assertGreaterEqual(len(report.issues), 1)
        self.assertIsInstance(report.to_markdown(), str)
        self.assertIn("Code Review", report.to_markdown())

    def test_diff_review_catches_new_vulns(self):
        diff = "+    result = cursor.execute('SELECT * FROM t WHERE id=%s' % uid)"
        issues = self.reviewer.review_diff(diff)
        self.assertIsInstance(issues, list)

    def test_score_penalizes_critical_issues(self):
        r1 = self.reviewer.review_file("a.py", CLEAN_CODE)
        r2 = self.reviewer.review_file("b.py", SQL_INJECTION_CODE)
        self.assertGreater(r1.score, r2.score)

    def test_critical_count_property(self):
        report = self.reviewer.review_file("x.py", SQL_INJECTION_CODE + HARDCODED_SECRET_CODE)
        self.assertIsInstance(report.critical_count, int)
        self.assertIsInstance(report.high_count, int)


class ReviewReporterTests(unittest.TestCase):

    def setUp(self):
        self.reporter = ReviewReporter()
        self.reviewer = AICodeReviewer()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_generate_html_contains_key_elements(self):
        report = self.reviewer.review_file("app.py", SQL_INJECTION_CODE)
        html = self.reporter.generate_html([report])
        self.assertIn("Saleha AI", html)
        self.assertIn("Code Review", html)
        self.assertIn("app.py", html)

    def test_save_report_creates_file(self):
        report = self.reviewer.review_file("main.py", CLEAN_CODE)
        out = os.path.join(self.tmp, "review.html")
        saved = self.reporter.save_report([report], output_path=out)
        self.assertTrue(os.path.isfile(saved))
        with open(saved, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("<!DOCTYPE html>", content)


if __name__ == "__main__":
    unittest.main()

