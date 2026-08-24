"""
Saleha Core: GitHub / GitLab Cloud Remote PR & Git Publisher

Automates pushing git branches to remote origins and opening Pull Requests
via GitHub CLI (`gh`) or direct GitHub REST API using GITHUB_TOKEN.
"""

import os
import re
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any


@dataclass
class GitHubPRResult:
    success: bool
    pr_url: str = ""
    pr_number: Optional[int] = None
    branch_name: str = ""
    message: str = ""
    error: str = ""


class GitHubIntegrator:
    def __init__(self, cwd: str = "."):
        self.cwd = os.path.abspath(cwd)

    def detect_remote_origin(self) -> Optional[Dict[str, str]]:
        """Parses git remote get-url origin to identify host, owner, and repo."""
        try:
            res = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                check=True
            )
            url = res.stdout.strip()
            clean_url = url[:-4] if url.endswith(".git") else url

            # Match HTTPS: https://github.com/owner/repo
            m_http = re.search(r"https?://([^/]+)/([^/]+)/(.+)$", clean_url)
            if m_http:
                return {"host": m_http.group(1), "owner": m_http.group(2), "repo": m_http.group(3), "raw_url": url}

            # Match SSH: git@github.com:owner/repo
            m_ssh = re.search(r"git@([^:]+):([^/]+)/(.+)$", clean_url)
            if m_ssh:
                return {"host": m_ssh.group(1), "owner": m_ssh.group(2), "repo": m_ssh.group(3), "raw_url": url}
        except (subprocess.SubprocessError, OSError):
            return None
        return None

    def push_branch(self, branch_name: str) -> Tuple[bool, str]:
        """Pushes the specified branch to remote origin."""
        try:
            res = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if res.returncode == 0:
                return True, res.stdout.strip()
            return False, res.stderr.strip()
        except Exception as e:
            return False, str(e)

    def create_pull_request(self, branch_name: str, title: str, body: str,
                            base_branch: str = "main") -> GitHubPRResult:
        """Opens a Pull Request on GitHub using gh CLI or GitHub REST API."""
        # 1. Try gh CLI first if available
        if shutil.which("gh"):
            try:
                res = subprocess.run(
                    ["gh", "pr", "create", "--base", base_branch, "--head", branch_name,
                     "--title", title, "--body", body],
                    cwd=self.cwd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if res.returncode == 0:
                    pr_url = res.stdout.strip()
                    m_num = re.search(r"/pull/(\d+)", pr_url)
                    pr_num = int(m_num.group(1)) if m_num else None
                    return GitHubPRResult(
                        success=True,
                        pr_url=pr_url,
                        pr_number=pr_num,
                        branch_name=branch_name,
                        message=f"Pull Request created successfully via GitHub CLI: {pr_url}"
                    )
            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                pass

        # 2. Fallback to GitHub REST API using GITHUB_TOKEN
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        remote_info = self.detect_remote_origin()

        if not remote_info:
            return GitHubPRResult(
                success=False,
                branch_name=branch_name,
                error="Could not detect git remote origin for repository."
            )

        if not token:
            return GitHubPRResult(
                success=False,
                branch_name=branch_name,
                error="GitHub CLI ('gh') is not installed and GITHUB_TOKEN environment variable is not set."
            )

        owner = remote_info["owner"]
        repo = remote_info["repo"]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "Saleha-AI-Agent"
        }
        payload = json.dumps({
            "title": title,
            "body": body,
            "head": branch_name,
            "base": base_branch
        }).encode("utf-8")

        req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return GitHubPRResult(
                    success=True,
                    pr_url=data.get("html_url", ""),
                    pr_number=data.get("number"),
                    branch_name=branch_name,
                    message=f"Pull Request created via GitHub API: {data.get('html_url')}"
                )
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8") if he.fp else str(he)
            return GitHubPRResult(success=False, branch_name=branch_name, error=f"GitHub API Error ({he.code}): {err_body}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            return GitHubPRResult(success=False, branch_name=branch_name, error=f"Failed to create GitHub PR: {str(e)}")
