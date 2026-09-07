"""
Tests for the GitHub issue -> fix branch resolver.

The previous suite had four tests and all of them passed `mock_solver=`,
which is the one argument that skipped the line where the module crashed:

    saleha resolve-issue 42
      -> NameError: name 'UnifiedDiffResult' is not defined

Every real invocation hit that. The tests never did, so a completely broken
production path sat green for as long as the module existed. The first test
below is the one that was missing: the default path, with no solver.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from saleha.core.issue_resolver import IssueResolver, GitHubIssue
from saleha.core.diff_engine import DiffResult, DiffHunk


def _temp_git_repo() -> str:
    path = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "config", "user.email", "t@example.com"],
                   check=True)
    subprocess.run(["git", "-C", path, "config", "user.name", "t"], check=True)
    with open(os.path.join(path, "seed.py"), "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    subprocess.run(["git", "-C", path, "add", "."], check=True)
    subprocess.run(["git", "-C", path, "commit", "-qm", "init"], check=True)
    return path


def _sample_diff() -> DiffResult:
    return DiffResult(
        file_path="auth.py",
        old_content="def old(): pass",
        new_content="def new(): pass",
        hunks=[DiffHunk(hunk_id=1, old_start=1, old_lines=["def old(): pass"],
                        new_start=1, new_lines=["def new(): pass"])],
        risk_score=1,
        risk_reason="Low risk",
        lines_added=1,
        lines_removed=1,
        unified_diff="--- a/auth.py\n+++ b/auth.py",
    )


class IssueParsingTests(unittest.TestCase):

    def setUp(self):
        self.resolver = IssueResolver()

    def test_fetch_issue_from_number_and_url(self):
        from_num = self.resolver.fetch_issue("105")
        self.assertIsNotNone(from_num)
        self.assertEqual(from_num.issue_number, 105)

        from_url = self.resolver.fetch_issue(
            "https://github.com/owner/repo/issues/42")
        self.assertIsNotNone(from_url)
        self.assertEqual(from_url.issue_number, 42)

    def test_fetch_issue_invalid_returns_none(self):
        self.assertIsNone(self.resolver.fetch_issue("invalid-non-numeric"))

    def test_unfetched_issue_is_marked_not_fetched(self):
        """
        The old code returned a placeholder issue indistinguishable from real
        data: title "Bug fix: Issue #N", a body it made up, and a github.com
        URL that pointed nowhere. Callers had no way to tell.
        """
        with patch("saleha.core.issue_resolver.subprocess.run",
                   side_effect=FileNotFoundError()):
            issue = self.resolver.fetch_issue("7")
        assert issue is not None
        self.assertFalse(issue.fetched)
        self.assertIn("gh", issue.fetch_error)
        self.assertEqual(issue.html_url, "")


class ResolvePipelineTests(unittest.TestCase):

    def setUp(self):
        self.repo = _temp_git_repo()
        self.resolver = IssueResolver(cwd=self.repo)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_default_path_runs_without_a_solver(self):
        """
        The regression test this module never had. Without `mock_solver` the
        old code reached `UnifiedDiffResult(...)`, a name defined nowhere in
        the repository, and raised NameError.
        """
        res = self.resolver.resolve_issue("999")
        self.assertIsNone(res.diff_result)
        self.assertIsNone(res.tests_passed)
        self.assertTrue(any("no code change" in c.lower() for c in res.caveats))

    def test_no_diff_is_ever_fabricated(self):
        """
        The old default produced a DiffResult for `fix_issue_999.py` claiming
        +10/-2 lines and risk 2. That file was never created and those numbers
        were invented.
        """
        res = self.resolver.resolve_issue("999")
        self.assertIsNone(res.diff_result)
        self.assertFalse(os.path.exists(
            os.path.join(self.repo, "fix_issue_999.py")))

    def test_tests_passed_is_none_when_no_command_is_given(self):
        """`test_output` used to be the constant string
        "All 12 unit tests passed in 0.42s" on every run."""
        res = self.resolver.resolve_issue("999")
        self.assertIsNone(res.tests_passed)
        self.assertNotIn("12 unit tests", res.test_output)

    def test_a_failing_test_command_makes_the_result_fail(self):
        res = self.resolver.resolve_issue(
            "999", branch_name="fail-branch",
            test_command=[sys.executable, "-c", "import sys; sys.exit(1)"])
        self.assertFalse(res.success)
        self.assertFalse(res.tests_passed)
        self.assertIn("not resolved", res.summary)

    def test_a_passing_test_command_is_reported_as_passing(self):
        res = self.resolver.resolve_issue(
            "999", branch_name="pass-branch",
            test_command=[sys.executable, "-c", "print('2 passed')"])
        self.assertTrue(res.success)
        self.assertTrue(res.tests_passed)
        self.assertIn("2 passed", res.test_output)

    def test_a_missing_test_command_is_reported_not_assumed(self):
        res = self.resolver.resolve_issue(
            "999", branch_name="missing-cmd",
            test_command=["definitely-not-a-real-binary-xyz"])
        self.assertIsNone(res.tests_passed)
        self.assertTrue(any("could not run" in c.lower() for c in res.caveats))

    def test_branch_is_actually_created(self):
        res = self.resolver.resolve_issue("321", branch_name="fix/mine")
        branches = subprocess.check_output(
            ["git", "-C", self.repo, "branch"], text=True)
        self.assertIn("fix/mine", branches)
        self.assertEqual(res.branch_name, "fix/mine")

    def test_branch_failure_is_reported_not_swallowed(self):
        """
        The old create_fix_branch caught everything and returned the branch
        name regardless, so a total failure to branch looked like success.
        """
        resolver = IssueResolver(cwd=self.repo)
        with patch("saleha.core.issue_resolver.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="fatal: nope")
            res = resolver.resolve_issue("5", branch_name="bad")
        self.assertFalse(res.success)
        self.assertIn("could not switch", res.error)

    def test_solver_result_is_carried_through(self):
        res = self.resolver.resolve_issue(
            "101", branch_name="with-solver", solver=lambda issue: _sample_diff())
        self.assertIsNotNone(res.diff_result)
        self.assertEqual(res.diff_result.file_path, "auth.py")

    def test_mock_solver_alias_still_works(self):
        """Kept so callers written against the old signature keep working."""
        res = self.resolver.resolve_issue(
            "101", branch_name="legacy", mock_solver=lambda issue: _sample_diff())
        assert res.diff_result is not None
        self.assertEqual(res.diff_result.file_path, "auth.py")


class PRBodyTests(unittest.TestCase):

    def setUp(self):
        self.resolver = IssueResolver()
        self.issue = GitHubIssue(
            issue_number=99,
            title="Fix null pointer crash in parser",
            body="Parser crashes on empty input strings.",
            html_url="https://github.com/test/repo/issues/99",
            fetched=True,
        )

    def test_body_includes_issue_context_and_diff(self):
        body = self.resolver.format_pr_body(
            self.issue, _sample_diff(), "2 passed", tests_passed=True)
        self.assertIn("#99", body)
        self.assertIn("Fix null pointer crash in parser", body)
        self.assertIn("auth.py", body)
        self.assertIn("2 passed", body)

    def test_body_says_nothing_was_verified_when_nothing_ran(self):
        """
        The old body printed the hardcoded "All 12 unit tests passed in 0.42s"
        under a "Verification Proof" heading -- and with --auto-pr that went
        onto a real pull request, telling reviewers a suite had passed.
        """
        body = self.resolver.format_pr_body(
            self.issue, None, "", tests_passed=None)
        self.assertIn("nothing here is verified", body)
        self.assertNotIn("Verification Proof", body)
        self.assertNotIn("All unit tests passed", body)
        self.assertNotIn("12 unit tests", body)

    def test_body_states_a_failing_test_run(self):
        body = self.resolver.format_pr_body(
            self.issue, _sample_diff(), "1 failed", tests_passed=False)
        self.assertIn("failed", body.lower())

    def test_body_flags_an_unfetched_issue(self):
        stub = GitHubIssue(issue_number=7, title="(issue #7 - not fetched)",
                           body="", fetched=False,
                           fetch_error="gh is not installed")
        body = self.resolver.format_pr_body(stub, None, "", tests_passed=None)
        self.assertIn("could not be fetched", body)
        self.assertIn("placeholder", body)

    def test_caveats_are_rendered(self):
        body = self.resolver.format_pr_body(
            self.issue, None, "", tests_passed=None,
            caveats=["No solver was supplied"])
        self.assertIn("Not established by this run", body)
        self.assertIn("No solver was supplied", body)


class FabricationRegressionTests(unittest.TestCase):
    """The specific strings and names that must never come back."""

    def test_the_undefined_name_is_gone(self):
        import saleha.core.issue_resolver as module
        source = open(module.__file__, encoding="utf-8").read()
        # It survives in the module docstring, which explains the defect.
        code = source.split('"""', 2)[-1]
        self.assertNotIn("UnifiedDiffResult(", code)

    def test_the_hardcoded_test_string_is_gone(self):
        import ast
        import saleha.core.issue_resolver as module
        tree = ast.parse(open(module.__file__, encoding="utf-8").read())
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        literals = "\n".join(
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value not in docstrings)
        self.assertNotIn("All 12 unit tests passed", literals)
        self.assertNotIn("Verification Proof", literals)


if __name__ == "__main__":
    unittest.main()
