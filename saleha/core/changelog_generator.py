"""
Saleha Core: Automated SemVer Changelog & Release Notes Generator

Parses conventional Git commits, categorizes features/fixes/refactors,
and synthesizes professional GitHub release notes and CHANGELOG.md documents.
"""

from __future__ import annotations

import os
import re
import time
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from saleha.core.git_native import git_engine


@dataclass
class ReleaseSection:
    features: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    refactors: List[str] = field(default_factory=list)
    performance: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    other: List[str] = field(default_factory=list)


class ChangelogGenerator:
    """Generates structured SemVer changelogs from Git commit logs."""

    def __init__(self, repo_dir: str = "."):
        self.repo_dir = os.path.abspath(repo_dir)

    def extract_recent_commits(self, limit: int = 50) -> List[str]:
        """Fetches commit messages from git log."""
        if not os.path.isdir(os.path.join(self.repo_dir, ".git")):
            return ["feat: Initialized Saleha AI Framework"]

        try:
            res = subprocess.run(
                ["git", "log", f"-n{limit}", "--pretty=format:%s"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            pass
        return ["feat: Initialized Saleha AI Framework"]

    def categorize_commits(self, commit_messages: List[str]) -> ReleaseSection:
        """Sorts commit messages into conventional commit categories."""
        section = ReleaseSection()

        for msg in commit_messages:
            low = msg.lower()
            if low.startswith("feat:") or low.startswith("feat("):
                clean = re.sub(r"^feat(?:\([^)]*\))?:\s*", "", msg, flags=re.IGNORECASE)
                section.features.append(clean)
            elif low.startswith("fix:") or low.startswith("fix("):
                clean = re.sub(r"^fix(?:\([^)]*\))?:\s*", "", msg, flags=re.IGNORECASE)
                section.fixes.append(clean)
            elif low.startswith("refactor:") or low.startswith("refactor("):
                clean = re.sub(r"^refactor(?:\([^)]*\))?:\s*", "", msg, flags=re.IGNORECASE)
                section.refactors.append(clean)
            elif low.startswith("perf:") or low.startswith("perf("):
                clean = re.sub(r"^perf(?:\([^)]*\))?:\s*", "", msg, flags=re.IGNORECASE)
                section.performance.append(clean)
            elif low.startswith("test:") or low.startswith("test("):
                clean = re.sub(r"^test(?:\([^)]*\))?:\s*", "", msg, flags=re.IGNORECASE)
                section.tests.append(clean)
            elif low.startswith("docs:") or low.startswith("docs("):
                clean = re.sub(r"^docs(?:\([^)]*\))?:\s*", "", msg, flags=re.IGNORECASE)
                section.docs.append(clean)
            else:
                section.other.append(msg)

        return section

    def generate_release_notes(self, version: str = "1.5.0", limit: int = 50) -> str:
        """Formats categorized commits into professional Markdown release notes."""
        commits = self.extract_recent_commits(limit=limit)
        cat = self.categorize_commits(commits)
        today = time.strftime("%Y-%m-%d")

        md = f"## [{version}] - {today}\n\n"

        if cat.features:
            md += "### 🚀 Features & Enhancements\n"
            for f in cat.features:
                md += f"- {f}\n"
            md += "\n"

        if cat.fixes:
            md += "### 🩹 Bug Fixes & Resilience\n"
            for fx in cat.fixes:
                md += f"- {fx}\n"
            md += "\n"

        if cat.refactors:
            md += "### 🔄 Architecture & Refactoring\n"
            for r in cat.refactors:
                md += f"- {r}\n"
            md += "\n"

        if cat.performance:
            md += "### ⚡ Performance Improvements\n"
            for p in cat.performance:
                md += f"- {p}\n"
            md += "\n"

        if cat.tests:
            md += "### 🧪 Quality Assurance & Tests\n"
            for t in cat.tests:
                md += f"- {t}\n"
            md += "\n"

        return md.strip()

    def update_changelog_file(self, file_path: str = "CHANGELOG.md", version: str = "1.5.0") -> str:
        """Appends new version release notes to CHANGELOG.md file."""
        notes = self.generate_release_notes(version=version)
        abs_p = os.path.join(self.repo_dir, file_path) if not os.path.isabs(file_path) else file_path

        existing = ""
        if os.path.isfile(abs_p):
            try:
                with open(abs_p, "r", encoding="utf-8") as fp:
                    existing = fp.read()
            except OSError:
                pass

        header = "# Changelog\n\nAll notable changes to Saleha AI Framework are documented here.\n\n"
        if not existing.startswith("# Changelog"):
            full_content = f"{header}{notes}\n\n{existing}"
        else:
            body = existing[len(header):] if existing.startswith(header) else existing
            full_content = f"{header}{notes}\n\n{body}"

        tmp_p = f"{abs_p}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as fp:
            fp.write(full_content.strip() + "\n")
        os.replace(tmp_p, abs_p)

        return abs_p


# Global instance
changelog_generator = ChangelogGenerator()
