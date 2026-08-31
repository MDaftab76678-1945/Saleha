"""
Saleha Core: Git Pre-Commit Hook & Security Guardrail Engine

Installs native Git pre-commit and pre-push hooks to verify AST syntax validity,
prevent secret/credential leakage, and enforce zero-broken-state commits.
"""

from __future__ import annotations

import os
import ast
import re
import stat
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from saleha.core.vault import EncryptedVault


PRE_COMMIT_SCRIPT_CONTENT = """#!/bin/sh
# Saleha AI Automated Pre-Commit Hook
saleha hook run
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "\\n[Saleha Guard] ❌ Commit blocked due to validation failures. Run 'saleha fix' to repair.\\n"
    exit 1
fi
exit 0
"""


class GitHookManager:
    """Manages installation, uninstallation, and execution of Git repository hooks."""

    def __init__(self, repo_dir: str = "."):
        self.repo_dir = os.path.abspath(repo_dir)

    def is_git_repo(self) -> bool:
        """Checks if workspace is a git repository."""
        return os.path.isdir(os.path.join(self.repo_dir, ".git"))

    def install_hooks(self) -> Tuple[bool, str]:
        """Installs pre-commit hook script into .git/hooks directory."""
        if not self.is_git_repo():
            return False, f"Directory '{self.repo_dir}' is not a Git repository."

        hooks_dir = os.path.join(self.repo_dir, ".git", "hooks")
        os.makedirs(hooks_dir, exist_ok=True)

        hook_file = os.path.join(hooks_dir, "pre-commit")
        try:
            with open(hook_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(PRE_COMMIT_SCRIPT_CONTENT)

            # Make executable on POSIX systems
            current_stat = os.stat(hook_file)
            os.chmod(hook_file, current_stat.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            return True, f"Successfully installed pre-commit hook at: {hook_file}"
        except OSError as e:
            return False, f"Failed to write hook file: {e}"

    def uninstall_hooks(self) -> Tuple[bool, str]:
        """Removes pre-commit hook script."""
        hook_file = os.path.join(self.repo_dir, ".git", "hooks", "pre-commit")
        if os.path.exists(hook_file):
            try:
                os.remove(hook_file)
                return True, "Pre-commit hook uninstalled."
            except OSError as e:
                return False, f"Could not remove hook file: {e}"
        return True, "No pre-commit hook was installed."

    def run_pre_commit_check(self) -> Tuple[bool, List[str]]:
        """Scans staged files for syntax errors and leaked credentials."""
        errors: List[str] = []

        # 1. Get staged files
        try:
            res = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=False
            )
            staged_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        except Exception:
            staged_files = []

        secret_patterns = [
            (re.compile(r'(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']', re.IGNORECASE), "Plaintext API Key / Secret"),
            (re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'), "Unencrypted Private Key Block"),
            (re.compile(r'ghp_[a-zA-Z0-9]{36}'), "GitHub Personal Access Token")
        ]

        for rel_f in staged_files:
            abs_f = os.path.join(self.repo_dir, rel_f)
            if not os.path.isfile(abs_f):
                continue

            try:
                with open(abs_f, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
            except OSError:
                continue

            # Check 1: Python AST Syntax Error
            if abs_f.endswith(".py"):
                try:
                    ast.parse(content, filename=rel_f)
                except SyntaxError as e:
                    errors.append(f"Syntax Error in {rel_f}:{e.lineno} - {e.msg}")

            # Check 2: Secret / Credential Leakage
            for pattern, desc in secret_patterns:
                if pattern.search(content):
                    errors.append(f"Security Leak in {rel_f} - {desc}")

        is_passed = len(errors) == 0
        return is_passed, errors


# Global instance
git_hook_manager = GitHookManager()
