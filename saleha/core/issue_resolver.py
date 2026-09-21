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

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from saleha.core.change_impact import ChangeImpactAnalyzer
from saleha.core.diff_engine import DiffEngine, DiffResult
from saleha.core.github_integrator import GitHubIntegrator, GitHubPRResult


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
        match = re.search(r"(\d+)$", issue_ref.strip())
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
                    labels=[lbl.get("name", "") for lbl in data.get("labels", [])],
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
                          custom_name: Optional[str] = None,
                          title: str = "") -> tuple[str, str]:
        """
        Create (or switch to) the fix branch.

        Returns (branch_name, error). The old version swallowed both the
        create and the fallback checkout, so a total failure to branch was
        indistinguishable from success.
        """
        if custom_name:
            branch_name = custom_name
        elif issue_number > 0:
            branch_name = f"fix/issue-{issue_number}"
        else:
            clean_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:30]
            suffix = clean_title if clean_title else "task"
            branch_name = f"fix/{suffix}"
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
        header_title = f"#{issue.issue_number}" if issue.issue_number > 0 else f"'{issue.title}'"
        body = [
            f"## Saleha: fix branch for {header_title}",
            "",
            "### Issue",
            f"**Title**: {issue.title}",
        ]
        if issue.html_url:
            body.append(f"**URL**: {issue.html_url}")
        if not issue.fetched and issue.fetch_error != "local task, not a GitHub issue":
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
            if diff_res.unified_diff:
                body += [
                    "",
                    "```diff",
                    diff_res.unified_diff[:2500].strip(),
                    "```",
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

    def _run_agent_solver(
        self,
        issue: GitHubIssue,
        model: str = "auto",
        max_steps: int = 15,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        auto_commit: bool = True,
        test_command: Optional[Sequence[str]] = None,
    ) -> Optional[DiffResult]:
        """
        Run AgentLoop to autonomously diagnose and fix the issue.
        Inspects git status to find modified files and computes a real DiffResult.
        """
        from saleha.agents.base_agent import BaseAgent
        from saleha.core.loop.agentic_loop import AgentLoop

        goal_parts = [f"Goal: Resolve issue - {issue.title}"]
        if issue.body:
            goal_parts.append(f"Issue description:\n{issue.body}")
        if test_command:
            goal_parts.append(f"Target test command to pass: {' '.join(test_command)}")
        goal_parts.append(
            "Instructions:\n"
            "1. Investigate the codebase using read tools (list_dir, read_file, get_file_outline, search_repo, find_symbols).\n"
            "2. Locate the bug, defect, or missing implementation.\n"
            "3. Apply minimal surgical patch using patch_file (or write_file if creating new file).\n"
            "4. Verify the fix using run_tests or run_code.\n"
            "5. Finish once verified."
        )
        goal = "\n\n".join(goal_parts)

        agent = BaseAgent(role="SoftwareEngineer", model=model)
        loop = AgentLoop(
            agent=agent,
            root_dir=self.cwd,
            max_steps=max_steps,
            allow_write=True,
            min_actions_before_finish=1,
        )

        loop.run(goal, on_event=on_event)

        # Query git status for modified or untracked files
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if status_proc.returncode != 0:
            return None

        lines = [line.strip() for line in status_proc.stdout.splitlines() if line.strip()]
        changed_files: List[str] = []
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                path_entry = parts[1].strip('"')
                if not path_entry.startswith(".saleha") and not path_entry.endswith(".saleha.bak"):
                    changed_files.append(path_entry)

        if not changed_files:
            return None

        primary_file = changed_files[0]
        abs_primary = os.path.join(self.cwd, primary_file)

        # Fetch old content from HEAD (or index)
        norm_file = primary_file.replace("\\", "/").lstrip("/")
        show_proc = subprocess.run(
            ["git", "show", f"HEAD:{norm_file}"],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        old_content = show_proc.stdout if show_proc.returncode == 0 and show_proc.stdout else ""
        if not old_content and show_proc.returncode != 0:
            index_proc = subprocess.run(
                ["git", "show", f":{norm_file}"],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if index_proc.returncode == 0 and index_proc.stdout:
                old_content = index_proc.stdout

        # Read new content from disk
        new_content = ""
        if os.path.exists(abs_primary):
            try:
                with open(abs_primary, "r", encoding="utf-8", errors="replace") as f:
                    new_content = f.read()
            except OSError:
                new_content = ""

        diff_res = self.diff_engine.compute_diff(primary_file, old_content, new_content)
        if len(changed_files) > 1:
            diff_res.file_path = f"{primary_file} (+{len(changed_files) - 1} other files)"

        if auto_commit:
            for cf in changed_files:
                subprocess.run(["git", "add", cf], cwd=self.cwd, capture_output=True)
            msg = f"fix: {issue.title}" if issue.title else f"fix: resolve issue #{issue.issue_number}"
            subprocess.run(["git", "commit", "-m", msg], cwd=self.cwd, capture_output=True)

        return diff_res

    def resolve_issue(
        self,
        issue_ref: str,
        branch_name: Optional[str] = None,
        auto_pr: bool = False,
        solver: Optional[Callable[[GitHubIssue], Optional[DiffResult]]] = None,
        test_command: Optional[Sequence[str]] = None,
        mock_solver: Optional[Callable[[GitHubIssue], Optional[DiffResult]]] = None,
        autonomous: bool = False,
        model: str = "auto",
        max_steps: int = 15,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        auto_commit: bool = True,
        issue_title: Optional[str] = None,
    ) -> IssueResolutionResult:
        """
        Fetch the issue, create the branch, optionally apply a caller-supplied
        solver or autonomous AgentLoop and run a test command, and render a PR description.

        `mock_solver` is the old name for `solver`, kept so existing callers
        keep working.
        """
        solver = solver or mock_solver
        caveats: List[str] = []

        issue = self.fetch_issue(issue_ref)
        if not issue:
            if issue_title:
                issue = GitHubIssue(
                    issue_number=0,
                    title=issue_title,
                    body=issue_ref if issue_ref != issue_title else "",
                    fetched=False,
                    fetch_error="local task, not a GitHub issue",
                )
            elif autonomous:
                first_line = issue_ref.strip().splitlines()[0][:80] if issue_ref.strip() else "Task"
                issue = GitHubIssue(
                    issue_number=0,
                    title=first_line,
                    body=issue_ref.strip(),
                    fetched=False,
                    fetch_error="local task, not a GitHub issue",
                )
            else:
                return IssueResolutionResult(
                    success=False,
                    issue=GitHubIssue(issue_number=0, title="", body=""),
                    branch_name="",
                    error=f"Could not parse an issue number from: {issue_ref}",
                )
        if not issue.fetched and issue.fetch_error != "local task, not a GitHub issue":
            caveats.append(
                f"Issue #{issue.issue_number} was not fetched "
                f"({issue.fetch_error}); its title and body are placeholders.")

        branch, branch_error = self.create_fix_branch(
            issue.issue_number, custom_name=branch_name, title=issue.title)
        if branch_error:
            return IssueResolutionResult(
                success=False, issue=issue, branch_name=branch,
                error=branch_error, caveats=caveats,
                summary=f"Failed before any change: {branch_error}",
            )

        # Solver execution: caller-supplied solver takes priority; otherwise, if
        # autonomous=True, run AgentLoop; otherwise produce no code changes.
        if solver:
            diff_result = solver(issue)
        elif autonomous:
            diff_result = self._run_agent_solver(
                issue=issue,
                model=model,
                max_steps=max_steps,
                on_event=on_event,
                auto_commit=auto_commit,
                test_command=test_command,
            )
        else:
            diff_result = None

        if diff_result is None:
            if autonomous:
                caveats.append(
                    "Autonomous solver ran but produced no code changes or modifications. "
                    "The branch is empty.")
            else:
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

        if issue.issue_number > 0:
            pr_title = f"fix: issue #{issue.issue_number}"
            if issue.fetched and issue.title:
                pr_title = f"fix: {issue.title} (#{issue.issue_number})"
        else:
            pr_title = f"fix: {issue.title}"

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
