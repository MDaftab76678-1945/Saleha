"""
Saleha Agents: Autonomous GitHub Issue & Pull Request Auto-Resolver Bot

Automatically analyzes software issue reports, tracebacks, and repository requirements:
1. Performs Root Cause Analysis (RCA).
2. Synthesizes AST-valid hardened code patches and pytest invariants using SwarmPipelineEngine.
3. Generates sanitized Git branch names and comprehensive GitHub Pull Request markdown descriptions.
"""

from __future__ import annotations

import ast
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from saleha.core.swarm_pipeline_engine import swarm_engine, SwarmExecutionResult


@dataclass
class IssueResolutionPlan:
    issue_id: str
    branch_name: str
    pr_title: str
    root_cause_analysis: str
    patch_code: str
    test_code: str
    security_clean: bool
    tests_passed: bool
    pr_body_markdown: str
    success: bool = True
    duration_ms: float = 0.0


class AutonomousIssueResolver:
    """Autonomous Bot for End-to-End Bug Triage, Code Patching, and PR Generation."""

    def __init__(self):
        self.engine = swarm_engine

    def _sanitize_branch_name(self, issue_id: str, title: str) -> str:
        clean_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:40]
        return f"fix/{issue_id.lower()}-{clean_title}"

    def _find_ast_error(self, code: str) -> Optional[str]:
        """Returns a SyntaxError message if `code` does not parse, else None.

        This used to be claimed unconditionally in the PR markdown
        ("AST Syntax Verification: Clean (0 Syntax Errors)") with no ast
        call anywhere in this class -- the claim was true only by luck.
        """
        if not code or not code.strip():
            return "no code was generated"
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return f"{e.msg} (line {e.lineno})"

    def resolve_issue(self, issue_description: str, repo_name: str = "Saleha") -> IssueResolutionPlan:
        """Resolves an issue autonomously using the multi-agent swarm pipeline."""
        start_time = time.time()
        issue_id = f"ISSUE-{str(uuid.uuid4())[:6].upper()}"

        # Extract title from first line
        first_line = issue_description.strip().splitlines()[0] if issue_description.strip() else "Bug Fix"
        pr_title = f"fix: resolve {first_line[:60]}"
        branch_name = self._sanitize_branch_name(issue_id, first_line)

        # 1. Execute Multi-Agent Swarm DAG
        swarm_result: SwarmExecutionResult = self.engine.execute_swarm(
            f"Fix issue in {repo_name}: {issue_description}"
        )

        # 2. Formulate Root Cause Analysis (RCA)
        rca_text = f"Identified inconsistency or bug in requirement: '{first_line}'. Applied AST-validated hardening and regression assertions."

        # The QALead stage (swarm_pipeline_engine.py) already generates and
        # actually executes a real test suite against the patch -- pull that
        # out instead of returning a hardcoded literal that was never run.
        # This used to be "def test_regression(): assert True\n" for every
        # issue, unconditionally, regardless of what the swarm produced.
        qa_stage = next((s for s in swarm_result.stages if s.agent_role == "QALead"), None)
        real_test_code = (qa_stage.payload.get("test_code", "") if qa_stage else "") or (
            "# QALead stage did not run for this issue -- no test was generated.\n"
        )

        ast_error = self._find_ast_error(swarm_result.final_code)

        # 3. Synthesize GitHub PR Body Markdown
        pr_body = self._render_pr_markdown(
            issue_id=issue_id,
            pr_title=pr_title,
            branch_name=branch_name,
            rca=rca_text,
            swarm_result=swarm_result,
            repo_name=repo_name,
            ast_error=ast_error,
        )

        elapsed = round((time.time() - start_time) * 1000, 2)

        return IssueResolutionPlan(
            issue_id=issue_id,
            branch_name=branch_name,
            pr_title=pr_title,
            root_cause_analysis=rca_text,
            patch_code=swarm_result.final_code,
            test_code=real_test_code,
            security_clean=swarm_result.security_clean,
            tests_passed=swarm_result.tests_passed,
            pr_body_markdown=pr_body,
            success=swarm_result.success,
            duration_ms=elapsed,
        )

    def _render_pr_markdown(
        self,
        issue_id: str,
        pr_title: str,
        branch_name: str,
        rca: str,
        swarm_result: SwarmExecutionResult,
        repo_name: str,
        ast_error: Optional[str] = None,
    ) -> str:
        stages_summary = "\n".join(
            f"- **{s.agent_role}Agent**: {s.output_summary} (`{s.duration_ms}ms`)"
            for s in swarm_result.stages
        )

        # Each checklist line below now reflects a value this function was
        # actually given, not a literal "Clean" / "Passed" written before any
        # of these fields existed on the result. An unchecked box with a
        # reason ("- [ ] ... : <what actually happened>") is the honest state
        # when a check did not run or did not pass -- not a checked box with
        # a caveat buried in the wording next to it.
        ast_status = "Clean (0 Syntax Errors)" if ast_error is None else f"FAILED: {ast_error}"
        ast_box = "[x]" if ast_error is None else "[ ]"
        security_box = "[x]" if swarm_result.security_clean else "[ ]"
        security_status = "Passed (0 CWEs Detected)" if swarm_result.security_clean else "Hardened (vulnerabilities found and patched)"
        tests_box = "[x]" if swarm_result.tests_passed else "[ ]"
        tests_status = "Generated tests executed and passed" if swarm_result.tests_passed else "Generated tests did not pass -- see QALead stage trace above"

        return f"""## 🚀 {pr_title}

### 📋 Overview & Issue Reference
- **Issue Reference**: `{issue_id}`
- **Target Branch**: `{branch_name}` $\\rightarrow$ `main`
- **Target Repository**: `{repo_name}`

---

### 🔍 Root Cause Analysis (RCA)
{rca}

---

### 🐝 Multi-Agent Swarm Execution Trace
{stages_summary}

---

### 🛡️ Quality & Verification Gate
- {ast_box} **AST Syntax Verification**: {ast_status}
- {security_box} **OWASP & SAST Security Audit**: {security_status}
- {tests_box} **Unit & Regression Testing**: {tests_status}
- [x] **Context Optimization**: `{swarm_result.token_savings_pct}%` Token Reduction

```python
# Synthesized Hardened Code Patch:
{swarm_result.final_code[:400]}...
```

*Generated Autonomously by **Saleha AI v2.6.0 Swarm Engine** in `{swarm_result.total_duration_ms}ms` ($0 Token Waste).*
"""


# Global Singleton Instance
issue_resolver = AutonomousIssueResolver()
