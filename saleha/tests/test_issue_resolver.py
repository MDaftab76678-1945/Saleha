"""Unit tests for Autonomous GitHub Issue-to-PR Auto-Resolver."""

from __future__ import annotations

import unittest
from saleha.core.issue_resolver import IssueResolver, GitHubIssue
from saleha.core.diff_engine import DiffResult, DiffHunk


class IssueResolverTests(unittest.TestCase):

    def setUp(self):
        self.resolver = IssueResolver()

    def test_fetch_issue_from_number_and_url(self):
        issue_from_num = self.resolver.fetch_issue("105")
        self.assertIsNotNone(issue_from_num)
        self.assertEqual(issue_from_num.issue_number, 105)

        issue_from_url = self.resolver.fetch_issue("https://github.com/owner/repo/issues/42")
        self.assertIsNotNone(issue_from_url)
        self.assertEqual(issue_from_url.issue_number, 42)

    def test_fetch_issue_invalid_returns_none(self):
        self.assertIsNone(self.resolver.fetch_issue("invalid-non-numeric"))

    def test_format_pr_body_includes_context_and_diff(self):
        issue = GitHubIssue(
            issue_number=99,
            title="Fix null pointer crash in parser",
            body="Parser crashes when encountering empty input strings.",
            html_url="https://github.com/test/repo/issues/99",
        )
        hunk = DiffHunk(hunk_id=1, old_start=10, old_lines=["line1"], new_start=10, new_lines=["line1", "line2"])
        diff = DiffResult(
            file_path="parser.py",
            old_content="old",
            new_content="new",
            hunks=[hunk],
            risk_score=2,
            risk_reason="Low risk change",
            lines_added=1,
            lines_removed=0,
            unified_diff="--- a/parser.py\n+++ b/parser.py",
        )
        body = self.resolver.format_pr_body(issue, diff, "All 8 tests passing.")

        self.assertIn("Fixes #99", body)
        self.assertIn("Fix null pointer crash in parser", body)
        self.assertIn("parser.py", body)
        self.assertIn("+1 / -0 lines", body)
        self.assertIn("All 8 tests passing.", body)

    def test_resolve_issue_pipeline_with_mock_solver(self):
        def custom_solver(iss):
            return DiffResult(
                file_path="auth.py",
                old_content="def old(): pass",
                new_content="def new(): pass",
                hunks=[],
                risk_score=1,
                risk_reason="Low risk",
                lines_added=3,
                lines_removed=0,
                unified_diff="--- a/auth.py\n+++ b/auth.py",
            )

        res = self.resolver.resolve_issue(
            issue_ref="101",
            branch_name="test-issue-101",
            auto_pr=False,
            mock_solver=custom_solver,
        )

        self.assertTrue(res.success)
        self.assertEqual(res.issue.issue_number, 101)
        self.assertEqual(res.branch_name, "test-issue-101")
        self.assertIsNotNone(res.diff_result)
        self.assertEqual(res.diff_result.file_path, "auth.py")
        self.assertIn("Successfully resolved issue #101", res.summary)


if __name__ == "__main__":
    unittest.main()

