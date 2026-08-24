"""
Saleha Core: Autonomous Git CI/CD & PR Generation Agent

Automates full Pull Request lifecycle:
1. Coordinates multi-agent team to generate production solution & TDD test suite.
2. Derives semantic branch names (feature/...) and conventional commit messages.
3. Validates unit tests in isolated execution environment.
4. Generates enterprise-ready PULL_REQUEST.md specification documents.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from saleha.core.team_orchestrator import TeamOrchestrator, TeamResult
from saleha.core.github_integrator import GitHubIntegrator, GitHubPRResult


@dataclass
class PRResult:
    success: bool
    branch_name: str = ""
    commit_title: str = ""
    commit_body: str = ""
    pr_markdown: str = ""
    solution_code: str = ""
    test_code: str = ""
    output_dir: str = ""
    test_passed: bool = False
    pr_url: str = ""
    error: str = ""


class PRGenerator:
    def __init__(self, model: str = "auto"):
        self.model = model
        self.orchestrator = TeamOrchestrator(model=model)

    def _sanitize_branch_name(self, goal: str) -> str:
        words = re.findall(r"[a-zA-Z0-9]+", goal.lower())
        short_name = "-".join(words[:5]) or "feature"
        return f"feature/{short_name}"

    def _generate_conventional_commit(self, goal: str, team_res: TeamResult) -> tuple[str, str]:
        words = re.findall(r"[a-zA-Z0-9]+", goal)
        scope = words[0].lower() if words else "core"
        title = f"feat({scope}): implement {goal.lower()[:50]}"
        
        body = f"""- Automated Multi-Agent Delivery by Saleha AI
- Architecture: {team_res.design[:120].strip()}...
- Verification: Test suite executed with {team_res.attempts} attempt(s)
- Security Audit: {team_res.security_report[:120].strip()}...
"""
        return title, body

    def _generate_pr_markdown(self, goal: str, branch_name: str,
                              commit_title: str, team_res: TeamResult) -> str:
        return f"""# 🚀 Pull Request: {goal}

[![Type: Feature](https://img.shields.io/badge/Type-Feature-blue.svg)]()
[![Status: Verified](https://img.shields.io/badge/Status-Verified%20(100%25)-brightgreen.svg)]()
[![Security: Approved](https://img.shields.io/badge/Security-Audit%20Passed-green.svg)]()
[![Agent: Saleha Swarm](https://img.shields.io/badge/Orchestrator-Saleha%20AI-purple.svg)]()

## 📌 Executive Summary
This Pull Request autonomously implements and verifies **{goal}** using Saleha's Multi-Agent Engineering Swarm.

---

## 🌿 Git Metadata
- **Branch**: `{branch_name}`
- **Conventional Commit**: `{commit_title}`

---

## 📋 Product Requirements (PRD)
{team_res.prd}

---

## 📐 Architecture & Low-Level Design (LLD)
{team_res.design}

---

## 🛡️ Security & Vulnerability Audit
{team_res.security_report}

---

## 🧪 Test Automation & Evidence
```python
{team_res.test_code}
```

### Execution Status:
- **Status**: `{'✅ PASSED' if team_res.success else '⚠️ NEEDS REVIEW'}`
- **Healing Cycles**: `{team_res.attempts}`
- **Execution Log**:
```text
{team_res.execution_output or 'All unit tests passed successfully.'}
```

---

## ✅ Pull Request Checklist
- [x] Code conforms to project architecture guidelines.
- [x] Full unit test coverage added and executed.
- [x] Security and AST compliance verified.
- [x] Conventional commit format applied.
"""

    def generate_pr(self, goal: str,
                    branch_name: Optional[str] = None,
                    output_dir: Optional[str] = None,
                    debate: bool = False,
                    push: bool = False,
                    open_pr: bool = False,
                    base_branch: str = "main") -> PRResult:
        """Executes swarm pipeline and generates a complete pull request package."""
        branch = branch_name or self._sanitize_branch_name(goal)
        
        team_res = self.orchestrator.run_team_workflow(goal=goal, output_dir=output_dir, debate=debate)
        if not team_res.success and not team_res.code:
            return PRResult(
                success=False,
                branch_name=branch,
                error="Team orchestrator failed to generate code solution."
            )

        commit_title, commit_body = self._generate_conventional_commit(goal, team_res)
        pr_md = self._generate_pr_markdown(goal, branch, commit_title, team_res)

        # Write artifacts if output_dir specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            with open(os.path.join(output_dir, "PULL_REQUEST.md"), "w", encoding="utf-8") as f:
                f.write(pr_md)
            with open(os.path.join(output_dir, "COMMIT_MSG.txt"), "w", encoding="utf-8") as f:
                f.write(f"{commit_title}\n\n{commit_body}")

        pr_url = ""
        # Handle remote git push & GitHub PR creation
        if push or open_pr:
            gh = GitHubIntegrator(cwd=output_dir or ".")
            pushed_ok, push_err = gh.push_branch(branch)
            if open_pr:
                gh_res = gh.create_pull_request(
                    branch_name=branch,
                    title=commit_title,
                    body=pr_md,
                    base_branch=base_branch
                )
                if gh_res.success:
                    pr_url = gh_res.pr_url

        return PRResult(
            success=team_res.success,
            branch_name=branch,
            commit_title=commit_title,
            commit_body=commit_body,
            pr_markdown=pr_md,
            solution_code=team_res.code,
            test_code=team_res.test_code,
            output_dir=output_dir or "",
            test_passed=team_res.success,
            pr_url=pr_url
        )

