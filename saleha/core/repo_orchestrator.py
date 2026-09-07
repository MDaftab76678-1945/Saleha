"""
AutonomousRepoOrchestrator: prepares a Git PR from real repository state.

## What this used to do

This module fabricated an entire pull request. Its own comment said
"Simulate file modifications and test verification", and what it returned was:

  * `files_modified` -- two invented paths derived from the goal slug
    (`saleha/core/<slug>.py`, `saleha/tests/test_<slug>.py`). Neither file was
    created, and neither typically existed.
  * `tests_passed=True` -- unconditionally, for every input. No test ever ran.
  * a PR body asserting "5/5 PASSED" in 12.4ms, "SecurityGuard SAST | 0
    Findings" in 3.1ms, "OWASP Top-10 SAST audit cleared with 0 CWE
    vulnerabilities", and "Pytest assertions verified inside Ephemeral
    Container Sandbox".

None of it happened. No branch was created, no file was written, no test or
scanner was invoked. The chat command on top of it printed "Branch Created"
and "100% Invariants Passed", so a user could paste a PR body claiming a
clean security audit into a real review.

Fabricating a passing test result is the most dangerous thing in this
codebase's failure catalogue: a wrong answer gets caught, a fake green does
not.

## What it does now

It reports the repository as it actually is, via `GitAutomationEngine`:

  * `files_modified` comes from `git status` -- the real uncommitted changes.
  * `tests_passed` is `None` unless a test run is supplied by the caller. It
    is never inferred, and `None` renders as "not run" rather than a tick.
  * the PR body describes the real diff, and states plainly which checks were
    not run instead of asserting they passed.
  * `branch_created` says whether a branch was really created, and outside a
    git repository the result says so rather than inventing a branch name.

Writing the branch is opt-in (`create_branch=True`), so merely rendering a PR
description cannot mutate the user's repository.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AutoPRResult:
    """The result of preparing a PR from real repository state."""
    task_goal: str
    branch_name: str
    commit_message: str
    pr_title: str
    pr_markdown_body: str
    files_modified: List[str]
    execution_time_ms: float
    # None means "no test run was supplied", which is not the same as passing.
    # The previous version hardcoded True here for every call.
    tests_passed: Optional[bool] = None
    # False when the branch was not actually created (not a repo, git failed,
    # or create_branch was not requested).
    branch_created: bool = False
    is_git_repo: bool = True
    # Checks this pipeline did not perform. Rendered into the PR body so the
    # reader is told what is unverified rather than being shown a fake pass.
    unverified: List[str] = field(default_factory=list)
    error: str = ""


class AutonomousRepoOrchestrator:
    """Prepares a branch, commit message and PR body from real git state."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def _engine(self):
        from saleha.core.git_native import GitAutomationEngine
        return GitAutomationEngine(repo_path=self.repo_path)

    @staticmethod
    def _slug(goal: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "-", goal.lower()).strip("-")[:35] or "task"

    def execute_auto_pr(
        self,
        task_goal: str,
        base_branch: str = "main",
        create_branch: bool = False,
        test_result: Optional[Dict[str, Any]] = None,
    ) -> AutoPRResult:
        """
        Prepare a PR for `task_goal` from the repository's real state.

        `create_branch` actually checks out a new branch; it is off by default
        so generating a description cannot mutate the repo.

        `test_result` is the only way `tests_passed` becomes non-None. Pass
        `{"passed": bool, "summary": str}` from a real run. Nothing here runs
        tests on its own, and nothing infers a pass -- which is exactly what
        the previous version did for every call.
        """
        start = time.perf_counter()
        slug = self._slug(task_goal)
        branch_name = f"feat/saleha-{slug}"
        pr_title = f"feat: {task_goal.strip()}"

        engine = self._engine()
        if not engine.is_git_repo():
            return AutoPRResult(
                task_goal=task_goal,
                branch_name="",
                commit_message="",
                pr_title=pr_title,
                pr_markdown_body=(
                    f"# {pr_title}\n\nNot a git repository "
                    f"(`{self.repo_path}`), so no branch, diff or PR could be "
                    f"prepared."
                ),
                files_modified=[],
                execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
                tests_passed=None,
                branch_created=False,
                is_git_repo=False,
                error="not a git repository",
            )

        status = engine.get_status_summary()
        files_modified = self._changed_paths(status)

        branch_created = False
        if create_branch:
            created = engine.create_task_branch(task_goal)
            if created:
                branch_name = created
                branch_created = True

        passed = None
        test_summary = ""
        if test_result is not None:
            passed = bool(test_result.get("passed"))
            test_summary = str(test_result.get("summary", "")).strip()

        unverified = []
        if passed is None:
            unverified.append("Tests were not run by this pipeline.")
        unverified.append("No SAST/security scan was run by this pipeline.")

        commit_message = self._commit_message(task_goal, files_modified, passed)
        body = self._render_pr_body(
            pr_title=pr_title, task_goal=task_goal, base_branch=base_branch,
            branch_name=branch_name, branch_created=branch_created,
            files_modified=files_modified, passed=passed,
            test_summary=test_summary, unverified=unverified,
        )

        return AutoPRResult(
            task_goal=task_goal,
            branch_name=branch_name,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_markdown_body=body,
            files_modified=files_modified,
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
            tests_passed=passed,
            branch_created=branch_created,
            is_git_repo=True,
            unverified=unverified,
        )

    @staticmethod
    def _changed_paths(status: Dict[str, Any]) -> List[str]:
        """
        Real changed paths from `git status --porcelain` lines.

        Porcelain format is `XY <path>`, and a rename is `R  old -> new`; the
        new name is the one a reviewer cares about.

        Deletions are skipped. A `D setup.py` line is a real change, but the
        path no longer exists on disk, and this list is consumed as "files you
        can open" -- reporting a path that cannot be opened is the same class
        of claim this module was rewritten to stop making.
        """
        paths = []
        for line in status.get("files", []) or []:
            entry = line.strip()
            if not entry:
                continue
            parts = entry.split(None, 1)
            code = parts[0] if len(parts) > 1 else ""
            path = parts[1] if len(parts) > 1 else parts[0]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            path = path.strip().strip('"')
            if "D" in code and not os.path.exists(path):
                continue
            paths.append(path)
        return paths

    @staticmethod
    def _commit_message(goal: str, files: List[str], passed: Optional[bool]) -> str:
        """
        A commit message that states only what is known.

        The old one asserted "Passed 100% invariant tests" and "Security SAST:
        0 vulnerabilities detected" on every call, regardless of whether
        anything ran.
        """
        lines = [f"feat: {goal.strip()}", ""]
        if files:
            lines.append(f"- {len(files)} file(s) changed in the working tree")
        else:
            lines.append("- no working-tree changes detected")
        if passed is True:
            lines.append("- test run reported passing")
        elif passed is False:
            lines.append("- test run reported FAILING")
        else:
            lines.append("- tests not run by this pipeline")
        return "\n".join(lines)

    @staticmethod
    def _render_pr_body(pr_title: str, task_goal: str, base_branch: str,
                        branch_name: str, branch_created: bool,
                        files_modified: List[str], passed: Optional[bool],
                        test_summary: str, unverified: List[str]) -> str:
        out = [f"## {pr_title}", "", "### Goal", task_goal.strip(), ""]

        out.append("### Branch")
        if branch_created:
            out.append(f"`{base_branch}` <- `{branch_name}` (created)")
        else:
            out.append(f"`{base_branch}` <- `{branch_name}` "
                       f"(proposed name; not created)")
        out.append("")

        out.append("### Changed files")
        if files_modified:
            out.extend(f"- `{f}`" for f in files_modified[:50])
            if len(files_modified) > 50:
                out.append(f"- ...and {len(files_modified) - 50} more")
        else:
            out.append("_No uncommitted changes in the working tree._")
        out.append("")

        out.append("### Verification")
        if passed is True:
            out.append(f"- Tests: PASSED{(' -- ' + test_summary) if test_summary else ''}")
        elif passed is False:
            out.append(f"- Tests: FAILED{(' -- ' + test_summary) if test_summary else ''}")
        for item in unverified:
            out.append(f"- {item}")
        out.append("")
        out.append("_Prepared by Saleha. Every line above reflects real "
                   "repository state; checks not run are listed as not run._")
        return "\n".join(out)


repo_orchestrator = AutonomousRepoOrchestrator()
