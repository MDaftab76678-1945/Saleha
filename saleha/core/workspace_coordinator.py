"""
Saleha Core: Multi-Repo & Monorepo Synchronized Workspace Coordinator

Discovers, audits, and coordinates synchronized git branches, commits, and status
checks across multiple repositories in a multi-repo engineering workspace.
"""

import os
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class RepoStatus:
    name: str
    path: str
    current_branch: str
    is_clean: bool
    uncommitted_count: int


class WorkspaceCoordinator:
    """Coordinates git actions across multi-repository workspaces."""

    def discover_repos(self, root_dir: str = ".") -> List[str]:
        """Finds all git repository directories under root."""
        repos = []
        # Check current directory
        if os.path.isdir(os.path.join(root_dir, ".git")):
            repos.append(os.path.abspath(root_dir))

        try:
            for item in os.listdir(root_dir):
                sub = os.path.join(root_dir, item)
                if os.path.isdir(sub) and os.path.isdir(os.path.join(sub, ".git")):
                    repos.append(os.path.abspath(sub))
        except OSError:
            pass

        # If no explicit .git sub-repos found, return root directory as fallback
        if not repos and os.path.isdir(root_dir):
            repos.append(os.path.abspath(root_dir))

        return list(dict.fromkeys(repos))

    def get_workspace_status(self, root_dir: str = ".") -> List[RepoStatus]:
        """Audits branch and uncommitted changes across all workspace repositories."""
        repo_paths = self.discover_repos(root_dir=root_dir)
        statuses = []

        for p in repo_paths:
            name = os.path.basename(p) or "root"
            branch = "main"
            is_clean = True
            uncommitted = 0

            try:
                # Get current branch
                b_proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=p, capture_output=True, text=True)
                if b_proc.returncode == 0:
                    branch = b_proc.stdout.strip()

                # Get status
                s_proc = subprocess.run(["git", "status", "--porcelain"], cwd=p, capture_output=True, text=True)
                if s_proc.returncode == 0:
                    lines = [l for l in s_proc.stdout.splitlines() if l.strip()]
                    uncommitted = len(lines)
                    is_clean = (uncommitted == 0)
            except Exception:
                pass

            statuses.append(RepoStatus(
                name=name,
                path=p,
                current_branch=branch,
                is_clean=is_clean,
                uncommitted_count=uncommitted
            ))

        return statuses

    def sync_branch(self, branch_name: str, root_dir: str = ".") -> Dict[str, bool]:
        """Creates or checks out a synchronized branch across all repos."""
        repo_paths = self.discover_repos(root_dir=root_dir)
        results = {}

        for p in repo_paths:
            name = os.path.basename(p) or "root"
            try:
                proc = subprocess.run(["git", "checkout", "-B", branch_name], cwd=p, capture_output=True, text=True)
                results[name] = (proc.returncode == 0)
            except Exception:
                results[name] = False

        return results


# Global instance
workspace_coordinator = WorkspaceCoordinator()

