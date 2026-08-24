"""
Saleha Skill: Git Automation & Release Helper

Provides fast local Git automation:
1. Conventional commit message formatting (feat, fix, docs, refactor, test, chore).
2. Standard Python `.gitignore` template generation.
3. Release notes & Markdown CHANGELOG generation.
4. Git command guidance and automation without requiring an LLM call.
"""

import os
import re
import subprocess
from typing import Optional, Dict, List

from saleha.core.skill_base import Skill, SkillResult


class GitSkill(Skill):
    name = "git_helper"
    description = "Git automation: conventional commit generation, .gitignore templates, branch workflows, and release changelogs."

    _GIT_KEYWORDS = {
        "git", "commit", "gitignore", "changelog", "release notes", "branch",
        "merge", "rebase", "stash", "pull request", "pr description"
    }

    def can_handle(self, task: str) -> bool:
        task_lower = task.strip().lower()
        if not any(k in task_lower for k in self._GIT_KEYWORDS):
            return False

        # Exclude general coding requests that just mention git in code
        if any(prefix in task_lower for prefix in ["write a python script to", "build an app", "create a function"]):
            return False

        patterns = [
            r"\b(git\s+(init|status|branch|checkout|commit|log|diff|push|pull))\b",
            r"\b(create|generate|write|format)\s+(a\s+)?(git\s+)?(commit\s+message|gitignore|\.gitignore|changelog|release\s+notes)\b",
            r"\b(conventional\s+commit)\b",
            r"\b(gitignore\s+for\s+python)\b",
        ]
        return any(re.search(p, task_lower) for p in patterns)

    def execute(self, task: str) -> SkillResult:
        task_lower = task.strip().lower()

        # 1. .gitignore generation
        if "gitignore" in task_lower:
            return self._generate_gitignore()

        # 2. Changelog / Release notes generation
        if "changelog" in task_lower or "release notes" in task_lower:
            return self._generate_changelog_template(task)

        # 3. Conventional Commit formatting
        if "commit" in task_lower:
            return self._generate_commit_message(task)

        # 4. Standard git commands guidance / execution
        if "git init" in task_lower:
            return SkillResult(
                success=True,
                output="Initialized empty Git repository.\nRun:\n  git init\n  git branch -M main\n  git add .\n  git commit -m 'chore: initial project scaffold'"
            )

        if "git branch" in task_lower or "checkout" in task_lower:
            match = re.search(r"(?:create|make|switch\s+to|checkout)\s+(?:branch\s+)?([a-zA-Z0-9_\-\/]+)", task, re.IGNORECASE)
            branch_name = match.group(1) if match else "feature/new-feature"
            return SkillResult(
                success=True,
                output=f"Git Branch Command:\n  git checkout -b {branch_name}\n  git push -u origin {branch_name}"
            )

        return SkillResult(
            success=True,
            output="Git Helper: Ready. Supported tasks: commit messages, .gitignore generation, branch workflows, changelog generation."
        )

    def _generate_gitignore(self) -> SkillResult:
        content = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
build/
dist/
*.egg-info/
*.egg

# Virtual environments
.env
.venv
env/
venv/
ENV/

# Testing & coverage
.coverage
htmlcov/
.pytest_cache/
.tox/

# IDE & OS files
.vscode/
.idea/
*.swp
*.swo
.DS_Store
Thumbs.db

# Saleha local session cache
.saleha_cache/
"""
        return SkillResult(
            success=True,
            output=f"Standard Python .gitignore:\n\n```gitignore\n{content}\n```"
        )

    def _generate_commit_message(self, task: str) -> SkillResult:
        # Determine conventional type
        commit_type = "feat"
        if any(w in task.lower() for w in ["fix", "bug", "error", "patch", "repair"]):
            commit_type = "fix"
        elif any(w in task.lower() for w in ["refactor", "cleanup", "structure"]):
            commit_type = "refactor"
        elif any(w in task.lower() for w in ["test", "unittest", "pytest"]):
            commit_type = "test"
        elif any(w in task.lower() for w in ["doc", "docs", "readme", "comment"]):
            commit_type = "docs"
        elif any(w in task.lower() for w in ["chore", "setup", "config", "build", "deps"]):
            commit_type = "chore"

        # Clean description
        cleaned = re.sub(r"(?i)^(generate|create|format|write|make)\s+(a\s+)?(git\s+)?(commit\s+message\s+(for\s+)?)?", "", task).strip()
        cleaned = cleaned.rstrip(".!?")
        if not cleaned:
            cleaned = "update codebase"

        msg = f"{commit_type}: {cleaned}"
        return SkillResult(
            success=True,
            output=f"Conventional Commit Message:\n\n  `{msg}`\n\nTo commit:\n  git commit -m \"{msg}\""
        )

    def _generate_changelog_template(self, task: str) -> SkillResult:
        template = """# CHANGELOG

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- Multi-agent collaborative team swarm pipeline (`saleha team`).
- Long-term persistent knowledge base & solution memory (`saleha memory`).
- Live operational Rich TUI dashboard (`saleha dashboard`, `saleha ui`).
- Dynamic Agent Profiles loaded from `saleha/skills/` (20 agent roles).
- Extensible local skills (`calculator`, `unit_converter`, `datetime_helper`, `git_helper`).

### Changed
- Self-healing execution loop with automated AST security verification.
- Smart router complexity-based dynamic model candidate selection.

### Fixed
- Fixed Windows charmap encoding across Rich CLI commands.
"""
        return SkillResult(
            success=True,
            output=f"Markdown Changelog Template:\n\n```markdown\n{template}\n```"
        )

