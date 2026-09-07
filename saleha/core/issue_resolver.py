"""
Saleha Core: GitHub issue -> local fix branch, with a PR description.

## What this module used to claim

The docstring said it "solves the problem using the autonomous self-healing
agent loop, runs tests to verify the fix, and opens a fully documented Pull
Request with diff preview and verification proof."

It did none of those things, and the default path did not run at all:

    saleha resolve-issue 42
      -> NameError: name 'UnifiedDiffResult' is not defined

`saleha/core/diff_engine.py` exports `DiffResult`; `UnifiedDiffResult` exists
nowhere in the repository. Every call without `mock_solver=` hit that line.
The four existing tests all passed `mock_solver`, so they never reached it --
the crash lived in production for as long as the module did.

Behind the crash, the rest was fabricated:

    test_out = "All 12 unit tests passed in 0.42s"   # no test ever ran
    additions=10, deletions=2, risk_score=2          # invented numbers
    success=True                                     # unconditional
    file_path=f"fix_issue_{n}.py"                    # a file that never exists

and `format_pr_body` printed that string under a "Verification Proof" heading.
With `--auto-pr` it would open a real pull request on a real repository
telling human reviewers a test suite had passed. That is the `/autopr` defect
(see the twelfth pass) in a second module.

## What it does now

It does the parts it can actually do, and reports the parts it cannot:

  - fetches the issue through `gh` when that works, and says so when it falls
    back to a stub rather than presenting the stub as fetched data;
  - creates the fix branch, and reports failure instead of swallowing it;
  - never invents a diff. A caller supplies the solver; without one, no code
    change is claimed;
  - runs the test command only if given one, and reports the real exit code.
    `tests_passed` is `Optional[bool]` and stays None when nothing ran.

`success` now means "the branch is ready", not "the issue is fixed" -- and
the summary says which. Nothing in this module can fix an issue on its own;
pretending otherwise is what the old version did.
"""

from __future__ import annotations

import os
import re
import json
import subprocess
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from saleha.core.github_integrator import GitHubIntegrator, GitHubPRResult
from saleha.core.diff_engine import DiffEngine, DiffResult
from saleha.core.change_impact import ChangeImpactAnalyzer


@dataclass
class GitHubIssue:
    issue_number: int
    title: str
    body: str
    author: str = ""
    labels: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    html_url: str = ""
    # False when `gh` could not be reached and the fields above are a
    # placeholder. The old code returned the placeholder indistinguishably
    # from real issue data.
    fetched: bool = False
    fetch_error: str = ""


@dataclass
class IssueResolutionResult:
    success: bool
    issue: GitHubIssue
    branch_name: str
    diff_result: Optional[DiffResult] = None
    pr_result: Optional[GitHubPRResult] = None
    test_output: str = ""
    # None means no test command was given, so nothing ran. It is never
    # inferred: the old code hardcoded a passing string.
    tests_passed: Optional[bool] = None
    summary: str = ""
    error: str = ""
    # What this run did not establish. Rendered into the PR body so a human
    # reviewer sees it.
    caveats: List[str] = field(default_factory=list)


class IssueResolver:
    """Turns a GitHub issue into a local fix branch and a PR description."""

    def __init__(self, cwd: str = ".", github_integrator: Optional[GitHubIntegrator] = None):
        self.cwd = os.path.abspath(cwd)
        self.github = github_integrator or GitHubIntegrator(cwd=self.cwd)
        self.diff_engine = DiffEngine()
        self.impact_analyzer = ChangeImpactAnalyzer()

    def fetch_issue(self, issue_ref: str) -> Optional[GitHubIssue]:
        """
        Fetch issue details through `gh issue view`.

        Accepts an issue number ('42') or a URL. When `gh` is unavailable or
        fails, a placeholder is returned with `fetched=False` and the reason
        in `fetch_error` -- callers must not treat it as issue data.
        """
        match = re.search(r"(\d+)$", str(issue_ref).strip())
        if not match:
            return None
        issue_num = int(match.group(1))

        reason = ""
        try:
            res = subprocess.run(
                ["gh", "issue", "view", str(issue_num), "--json",
                 "number,title,body,author,labels,comments,url"],
                cwd=self.cwd, capture_output=True, text=True, timeout=10,
            )
            if res.returncode == 0:
                data = json.loads(res.stdout)
                return GitHubIssue(
                    issue_number=data.get("number", issue_num),
                    title=data.get("title", f"Issue #{issue_num}"),
                    body=data.get("body", ""),
                    author=(data.get("author") or {}).get("login", ""),
                    labels=[l.get("name", "") for l in data.get("labels", [])],
                    comments=[c.get("body", "") for c in data.get("comments", [])],
                    html_url=data.get("url", ""),
                    fetched=True,
                )
            reason = (res.stderr or res.stdout or "").strip()[:200] or \
                     f"gh exited {res.returncode}"
        except FileNotFoundError:
            reason = "the GitHub CLI (`gh`) is not installed"
        except subprocess.SubprocessError as exc:
            reason = f"{type(exc).__name__}: {exc}"
        except (ValueError, json.JSONDecodeError) as exc:
            reason = f"could not parse gh output: {exc}"

        return GitHubIssue(
            issue_number=issue_num,
            title=f"(issue #{issue_num} - not fetched)",
            body="",
            html_url="",
            fetched=False,
            fetch_error=reason,
        )

    def create_fix_branch(self, issue_number: int,
                          custom_name: Optional[str] = None) -> tuple[str, str]:
        """
        Create (or switch to) the fix branch.

        Returns (branch_name, error). The old version swallowed both the
        create and the fallback checkout, so a total failure to branch was
        indistinguishable from success.
        """
        branch_name = custom_name or f"fix/issue-{issue_number}"
        created = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.cwd, capture_output=True, text=True,
        )
        if created.returncode == 0:
            return branch_name, ""

        existing = subprocess.run(
            ["git", "checkout", branch_name],
            cwd=self.cwd, capture_output=True, text=True,
        )
        if existing.returncode == 0:
            return branch_name, ""

        detail = (existing.stderr or created.stderr or "").strip()[:200]
        return branch_name, f"could not switch to '{branch_name}': {detail}"

    def run_tests(self, command: Sequence[str],
                  timeout: int = 900) -> tuple[Optional[bool], str]:
        """
        Run the caller's test command and report the real result.

        Returns (passed, output). `passed` is None only when the command could
        not be run at all -- never a default.
        """
        try:
            proc = subprocess.run(
                list(command), cwd=self.cwd, capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace",
            )
        except FileNotFoundError:
            return None, f"test command not found: {command[0]}"
        except subprocess.TimeoutExpired:
            return False, f"test command timed out after {timeout}s"
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"could not run tests: {type(exc).__name__}: {exc}"

        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return proc.returncode == 0, output or f"exit {proc.returncode}"

    def format_pr_body(
        self,
        issue: GitHubIssue,
        diff_res: Optional[DiffResult],
        test_summary: str,
        tests_passed: Optional[bool] = None,
        caveats: Optional[List[str]] = None,
    ) -> str:
        """
        Render the PR description.

        The verification section states what actually ran. Previously it
        printed a hardcoded "All 12 unit tests passed in 0.42s" under a
        "Verification Proof" heading, on a run where no test existed.
        """
        body = [
            f"## Saleha: fix branch for #{issue.issue_number}",
            "",
            "### Issue",
            f"**Title**: {issue.title}",
        ]
        if issue.html_url:
            body.append(f"**URL**: {issue.html_url}")
        if not issue.fetched:
            body.append(
                f"\n> Issue details could not be fetched "
                f"({issue.fetch_error or 'reason not recorded'}). "
                f"The title above is a placeholder, not the real issue."
            )
        elif issue.body:
            excerpt = issue.body[:300] + ("..." if len(issue.body) > 300 else "")
            body.append(f"\n> {excerpt}")

        body += ["", "---", "", "### Changes"]
        if diff_res:
            body += [
                f"- **File**: `{diff_res.file_path}`",
                f"- **Diff**: `{diff_res.change_summary}`",
                f"- **Risk**: `{diff_res.risk_score}/10` ({diff_res.risk_reason})",
            ]
        else:
            body.append(
                "- No code change was produced by this run. The branch is "
                "empty; the fix still has to be written."
            )

        body += ["", "---", "", "### Verification"]
        if tests_passed is None:
            body.append(
                "No test command was run, so nothing here is verified.")
        elif tests_passed:
            body.append("Test command exited 0:")
        else:
            body.append("Test command **failed**:")
        if test_summary.strip():
            body += ["", "```", test_summary.strip()[:2000], "```"]

        if caveats:
            body += ["", "---", "", "### Not established by this run"]
            body += [f"- {c}" for c in caveats]

        return "\n".join(body) + "\n"

    def resolve_issue(
        self,
        issue_ref: str,
        branch_name: Optional[str] = None,
        auto_pr: bool = False,
        solver: Optional[Callable[[GitHubIssue], Optional[DiffResult]]] = None,
        test_command: Optional[Sequence[str]] = None,
        mock_solver: Optional[Callable[[GitHubIssue], Optional[DiffResult]]] = None,
    ) -> IssueResolutionResult:
        """
        Fetch the issue, create the branch, optionally apply a caller-supplied
        solver and run a test command, and render a PR description.

        `mock_solver` is the old name for `solver`, kept so existing callers
        keep working.
        """
        solver = solver or mock_solver
        caveats: List[str] = []

        issue = self.fetch_issue(issue_ref)
        if not issue:
            return IssueResolutionResult(
                success=False,
                issue=GitHubIssue(issue_number=0, title="", body=""),
                branch_name="",
                error=f"Could not parse an issue number from: {issue_ref}",
            )
        if not issue.fetched:
            caveats.append(
                f"Issue #{issue.issue_number} was not fetched "
                f"({issue.fetch_error}); its title and body are placeholders.")

        branch, branch_error = self.create_fix_branch(
            issue.issue_number, custom_name=branch_name)
        if branch_error:
            return IssueResolutionResult(
                success=False, issue=issue, branch_name=branch,
                error=branch_error, caveats=caveats,
                summary=f"Failed before any change: {branch_error}",
            )

        # No solver means no code change. The old version fabricated a diff
        # here describing a file it never created.
        diff_result = solver(issue) if solver else None
        if diff_result is None:
            caveats.append(
                "No solver was supplied, so no code change was produced. "
                "The branch is empty.")

        tests_passed: Optional[bool] = None
        test_out = ""
        if test_command:
            tests_passed, test_out = self.run_tests(test_command)
            if tests_passed is None:
                caveats.append(f"The test command could not run: {test_out}")
        else:
            caveats.append(
                "No test command was given, so nothing was verified. "
                "Pass test_command= to run one.")

        pr_title = f"fix: issue #{issue.issue_number}"
        if issue.fetched and issue.title:
            pr_title = f"fix: {issue.title} (#{issue.issue_number})"
        pr_body = self.format_pr_body(
            issue, diff_result, test_out, tests_passed, caveats)

        if auto_pr:
            pr_res = self.github.create_pull_request(
                title=pr_title, body=pr_body, branch_name=branch)
        else:
            pr_res = GitHubPRResult(
                success=True, branch_name=branch,
                message="Fix branch ready locally "
                        "(use --auto-pr to publish to GitHub)",
            )

        # success means the branch is ready, not that the issue is fixed. A
        # failing test run is a real failure; everything else this module
        # could not establish is reported through `caveats`.
        succeeded = tests_passed is not False
        if tests_passed is False:
            summary = (f"Branch '{branch}' created, but the test command "
                       f"failed. The issue is not resolved.")
        elif diff_result is None:
            summary = (f"Branch '{branch}' created. No code change was made; "
                       f"the fix still has to be written.")
        elif tests_passed:
            summary = (f"Branch '{branch}' has a change and the test command "
                       f"passed.")
        else:
            summary = (f"Branch '{branch}' has a change. Nothing was "
                       f"verified: no test command was run.")

        return IssueResolutionResult(
            success=succeeded,
            issue=issue,
            branch_name=branch,
            diff_result=diff_result,
            pr_result=pr_res,
            test_output=test_out,
            tests_passed=tests_passed,
            summary=summary,
            caveats=caveats,
        )


# Global instance
issue_resolver = IssueResolver()
