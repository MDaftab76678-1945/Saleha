"""
Saleha Core: Git-Native Autonomous Commit & History Reversal Engine

Provides automated, conventional Git commits for verified agent task deliverables,
automatic branch isolation, and safe atomic undo/rollback capabilities (Aider-style).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set


@dataclass
class GitCommitResult:
    success: bool
    commit_hash: str = ""
    branch: str = ""
    message: str = ""
    files_changed: List[str] = field(default_factory=list)
    error: str = ""


class GitAutomationEngine:
    """Automates Git operations for autonomous AI programming workflows."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        self.git_bin = shutil.which("git") or "git"
        self._active_worktrees: Set[str] = set()
        import atexit
        atexit.register(self._cleanup_all_worktrees)

    def _cleanup_all_worktrees(self):
        """Cleanup handler registered with atexit to remove ephemeral worktrees on process termination."""
        for wt in list(self._active_worktrees):
            try:
                self.remove_worktree(wt, force=True)
            except Exception:
                pass

    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.git_bin] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False
            )
        except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
            return subprocess.CompletedProcess(
                args=[self.git_bin] + args,
                returncode=1,
                stdout="",
                stderr=str(e)
            )

    def is_git_repo(self) -> bool:
        res = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return res.returncode == 0 and res.stdout.strip() == "true"

    def get_current_branch(self) -> str:
        if not self.is_git_repo():
            return ""
        res = self._run_git(["branch", "--show-current"])
        return res.stdout.strip()

    def get_status_summary(self) -> Dict[str, Any]:
        if not self.is_git_repo():
            return {"is_repo": False}
        res = self._run_git(["status", "--porcelain"])
        dirty_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        return {
            "is_repo": True,
            "branch": self.get_current_branch(),
            "dirty": len(dirty_files) > 0,
            "dirty_count": len(dirty_files),
            "files": dirty_files[:20]
        }

    def create_task_branch(self, goal: str) -> str:
        """Generates a clean semantic branch name and checks it out."""
        if not self.is_git_repo():
            return ""
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', goal.lower()).strip('-')[:30]
        branch_name = f"saleha/{slug or 'task'}"
        self._run_git(["checkout", "-B", branch_name])
        return branch_name

    def format_conventional_message(self, goal: str, task_type: str = "feat",
                                   model: Optional[str] = None, test_passed: bool = True) -> str:
        """Constructs a standard Conventional Commits formatted commit message."""
        clean_goal = goal.strip().replace("\n", " ")
        # Determine scope
        scope = "core"
        lower_goal = clean_goal.lower()
        if any(w in lower_goal for w in ["api", "endpoint", "route", "graphql", "rest"]):
            scope = "api"
        elif any(w in lower_goal for w in ["ui", "css", "html", "react", "view", "frontend"]):
            scope = "ui"
        elif any(w in lower_goal for w in ["auth", "jwt", "oauth", "password", "login", "crypto", "auth token"]):
            scope = "auth"
        elif any(w in lower_goal for w in ["test", "mock", "qa", "unittest", "pytest"]):
            scope = "test"

        header = f"{task_type}({scope}): {clean_goal[:70]}"
        body = [
            f"Goal: {clean_goal}",
            f"Model: {model or 'local-llm'}",
            f"Verified: {'Passed AST & Execution Tests' if test_passed else 'Unverified'}",
            "",
            "🤖 Generated & self-healed by Saleha AI Autonomous Platform"
        ]
        return f"{header}\n\n" + "\n".join(body)

    def auto_commit_task(self, goal: str, files: Optional[List[str]] = None,
                         task_type: str = "feat", model: Optional[str] = None,
                         test_passed: bool = True) -> GitCommitResult:
        """Stages changed files and creates an atomic conventional commit.

        B2: SALEHA_APPROVAL=dangerous/always mode me yeh HITL approval
        maangta hai (deny -> commit skip, error return).
        """
        from saleha.core.approval_gate import approve
        if not approve("git_commit", f"Auto-commit for goal: {goal[:100]}"):
            return GitCommitResult(success=False, error="Commit denied by human-approval gate.")

        if not self.is_git_repo():
            return GitCommitResult(success=False, error="Directory is not a Git repository.")

        # Stage files
        if files:
            stage_args = ["add"] + files
        else:
            stage_args = ["add", "."]
        stage_res = self._run_git(stage_args)
        if stage_res.returncode != 0:
            return GitCommitResult(success=False, error=f"Git add failed: {stage_res.stderr}")

        # Check if there are staged changes
        diff_res = self._run_git(["diff", "--cached", "--name-only"])
        staged_files = [f.strip() for f in diff_res.stdout.splitlines() if f.strip()]
        if not staged_files:
            return GitCommitResult(success=True, message="No changes to commit.", files_changed=[])

        commit_msg = self.format_conventional_message(goal, task_type=task_type, model=model, test_passed=test_passed)
        commit_res = self._run_git(["commit", "-m", commit_msg])

        if commit_res.returncode != 0:
            return GitCommitResult(success=False, error=f"Git commit failed: {commit_res.stderr}")

        hash_res = self._run_git(["rev-parse", "--short", "HEAD"])
        commit_hash = hash_res.stdout.strip()
        current_branch = self.get_current_branch()

        return GitCommitResult(
            success=True,
            commit_hash=commit_hash,
            branch=current_branch,
            message=commit_msg,
            files_changed=staged_files
        )

    def rollback_last_commit(self, soft: bool = True) -> Dict[str, Any]:
        """Aider-style safe undo to revert the last commit."""
        if not self.is_git_repo():
            return {"success": False, "error": "Not a Git repository."}

        # Get last commit details
        last_log = self._run_git(["log", "-1", "--pretty=format:%h %s"])
        if last_log.returncode != 0 or not last_log.stdout.strip():
            return {"success": False, "error": "No commits found to revert."}

        last_info = last_log.stdout.strip()
        reset_flag = "--soft" if soft else "--hard"
        res = self._run_git(["reset", reset_flag, "HEAD~1"])

        if res.returncode == 0:
            return {
                "success": True,
                "reverted_commit": last_info,
                "mode": reset_flag,
                "message": f"Successfully reverted last commit: {last_info} ({reset_flag})"
            }
        return {"success": False, "error": res.stderr}

    def create_worktree(self, branch_name: str, target_dir: Optional[str] = None) -> Tuple[bool, str, str]:
        """Creates an isolated git worktree directory for safe multi-agent execution."""
        if not self.is_git_repo():
            return False, "", "Not a git repository"

        wt_path = target_dir or os.path.join(tempfile.gettempdir(), f"saleha_wt_{branch_name.replace('/', '_')}")
        res = self._run_git(["worktree", "add", "-B", branch_name, wt_path])
        if res.returncode == 0 or os.path.isdir(wt_path):
            self._active_worktrees.add(wt_path)
            return True, wt_path, ""
        return False, "", res.stderr

    def remove_worktree(self, worktree_dir: str, force: bool = True) -> Tuple[bool, str]:
        """Removes an ephemeral git worktree safely."""
        if not self.is_git_repo():
            return False, "Not a git repository"
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(worktree_dir)
        res = self._run_git(args)
        if res.returncode == 0 or not os.path.exists(worktree_dir):
            self._active_worktrees.discard(worktree_dir)
            return True, ""
        return False, res.stderr


# Global instance
git_engine = GitAutomationEngine()


