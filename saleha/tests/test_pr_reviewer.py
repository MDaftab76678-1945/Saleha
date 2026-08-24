"""Unit tests for GitHub PR Auto-Reviewer & CI Bot."""

import unittest
from saleha.core.pr_reviewer import PRReviewer


class PRReviewerTests(unittest.TestCase):

    def setUp(self):
        self.reviewer = PRReviewer()

    def test_review_diff_clean_code(self):
        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def greet(name: str) -> str:\n"
            "+    return f'Hello, {name}'\n"
        )
        report = self.reviewer.review_diff(diff, pr_title="Add greeting function")
        self.assertEqual(report.risk_level, "LOW")
        self.assertEqual(report.merge_decision, "APPROVE")
        self.assertEqual(len(report.files_analyzed), 1)
        self.assertIn("app.py", report.files_analyzed)
        self.assertEqual(len(report.security_findings), 0)

    def test_review_diff_with_security_vulnerability(self):
        diff = (
            "diff --git a/auth.py b/auth.py\n"
            "--- a/auth.py\n"
            "+++ b/auth.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+import os\n"
            "+def run_cmd(user_input):\n"
            "+    eval(user_input)\n"
        )
        report = self.reviewer.review_diff(diff, pr_title="Vulnerable eval PR")
        self.assertEqual(report.risk_level, "HIGH")
        self.assertEqual(report.merge_decision, "REQUEST_CHANGES")
        self.assertTrue(len(report.security_findings) >= 1)

    def test_empty_diff_returns_comment(self):
        report = self.reviewer.review_diff("", pr_title="Empty PR")
        self.assertEqual(report.merge_decision, "COMMENT")


if __name__ == "__main__":
    unittest.main()

