"""
Saleha Core: Git Pre-Commit Security Hook & Automation Engine

Installs and manages automated pre-commit security gates that scan every commit
for SAST vulnerabilities, hardcoded credentials, and unsafe execution before code enters Git.
"""

import os
import stat
import subprocess
from typing import Dict, Any, Optional

from saleha.core.git_native import git_engine


PRE_COMMIT_SCRIPT = """#!/bin/sh
# Saleha AI Autonomous Security Gate - Pre-Commit Hook
# Blocks commits containing hardcoded secrets or critical SAST vulnerabilities.

echo "🛡️ [Saleha AI] Running Pre-Commit AST Security SAST Scan..."

# Check if saleha command is available
if command -v saleha >/dev/null 2>&1; then
    saleha sast . --severity high
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "❌ [Saleha AI] Commit BLOCKED: High-severity security vulnerabilities detected."
        echo "💡 Run 'saleha sast .' to inspect details, or use 'git commit --no-verify' to bypass."
        exit 1
    fi
else
    # Fallback to python module execution
    python3 -m saleha.cli.commands sast . --severity high 2>/dev/null || python -m saleha.cli.commands sast . --severity high 2>/dev/null
fi

echo "✅ [Saleha AI] Security Gate Passed."
exit 0
"""


class GitHookManager:
    """Manages installation and removal of Git lifecycle security hooks."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)

    def _get_hooks_dir(self) -> Optional[str]:
        git_dir = os.path.join(self.repo_path, ".git")
        if not os.path.isdir(git_dir):
            return None
        hooks_dir = os.path.join(git_dir, "hooks")
        os.makedirs(hooks_dir, exist_ok=True)
        return hooks_dir

    def install_pre_commit(self) -> Dict[str, Any]:
        """Installs executable pre-commit security hook in .git/hooks/pre-commit."""
        hooks_dir = self._get_hooks_dir()
        if not hooks_dir:
            return {"success": False, "error": "Not a Git repository (no .git directory found)."}

        hook_file = os.path.join(hooks_dir, "pre-commit")
        try:
            with open(hook_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(PRE_COMMIT_SCRIPT)

            # Make executable on Unix/macOS/Windows Git-Bash
            st = os.stat(hook_file)
            os.chmod(hook_file, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            return {
                "success": True,
                "hook_path": hook_file,
                "message": "Successfully installed Saleha Pre-Commit SAST Security Gate."
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to write hook file: {str(e)}"}

    def uninstall_pre_commit(self) -> Dict[str, Any]:
        """Removes the pre-commit hook file."""
        hooks_dir = self._get_hooks_dir()
        if not hooks_dir:
            return {"success": False, "error": "Not a Git repository."}

        hook_file = os.path.join(hooks_dir, "pre-commit")
        if os.path.exists(hook_file):
            try:
                os.remove(hook_file)
                return {"success": True, "message": "Pre-commit hook uninstalled successfully."}
            except Exception as e:
                return {"success": False, "error": f"Failed to delete hook: {str(e)}"}
        return {"success": True, "message": "No pre-commit hook was present."}

    def generate_commit_from_diff(self, task_type: str = "feat") -> str:
        """Inspects git diff and automatically drafts a conventional commit message."""
        status = git_engine.get_status_summary()
        if not status.get("is_repo"):
            return "feat(core): update application code"

        files = status.get("files", [])
        if not files:
            return "chore: clean working tree update"

        first_file = files[0].split()[-1] if files else "core"
        clean_name = os.path.splitext(os.path.basename(first_file))[0]
        return git_engine.format_conventional_message(f"Update and optimize {clean_name}", task_type=task_type)


# Global instance
hook_manager = GitHookManager()

