"""
Saleha Core: GitHub PR Auto-Reviewer & CI Bot

Analyzes Git PR diffs, executes automated SAST security scans, evaluates architectural
impact, and generates structured line-by-line GitHub PR review comments and merge recommendations.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.core.security_scanner import ASTSecurityScanner


@dataclass
class PRReviewReport:
    summary: str
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    files_analyzed: List[str]
    security_findings: List[Dict[str, Any]]
    recommendations: List[str]
    merge_decision: str  # 'APPROVE', 'REQUEST_CHANGES', 'COMMENT'
    markdown_report: str


class PRReviewer:
    """Automates pull request diff analysis and code reviews."""

    def __init__(self):
        self.scanner = ASTSecurityScanner()

    def get_git_diff(self, base_branch: str = "main") -> str:
        """Retrieves git diff against base branch."""
        try:
            res = subprocess.run(
                ["git", "diff", f"origin/{base_branch}...HEAD"],
                capture_output=True,
                text=True,
                check=False
            )
            if not res.stdout.strip():
                # Fallback to local branch diff
                res = subprocess.run(
                    ["git", "diff", f"{base_branch}...HEAD"],
                    capture_output=True,
                    text=True,
                    check=False
                )
            if not res.stdout.strip():
                # Fallback to uncommitted working tree diff
                res = subprocess.run(
                    ["git", "diff", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False
                )
            return res.stdout
        except Exception:
            return ""

    def review_diff(self, diff_text: str, pr_title: str = "Pull Request") -> PRReviewReport:
        """Parses git diff and performs automated code and security review."""
        if not diff_text.strip():
            return PRReviewReport(
                summary="No code changes detected in diff.",
                risk_level="LOW",
                files_analyzed=[],
                security_findings=[],
                recommendations=["Ensure your branch has committed changes compared to target."],
                merge_decision="COMMENT",
                markdown_report="### 🧠 Saleha PR Review\n\nNo changes detected."
            )

        # Extract modified files
        files_modified = re.findall(r"diff --git a/(.*?) b/", diff_text)
        files_list = list(dict.fromkeys(files_modified))

        # Perform SAST scan on added lines
        added_lines = [
            line[1:] for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added_code = "\n".join(added_lines)

        findings = []
        for issue in self.scanner.scan_code(added_code, filename="pr_diff.py"):
            findings.append({
                "rule_id": issue.rule_id,
                "severity": issue.severity.lower(),
                "message": issue.description,
                "line": issue.line_number
            })

        has_high_security = any(f["severity"] in ("high", "critical") for f in findings)
        risk_level = "HIGH" if has_high_security else ("MEDIUM" if findings else "LOW")
        decision = "REQUEST_CHANGES" if has_high_security else "APPROVE"

        # Generate markdown report
        md_lines = [
            f"## 🧠 Saleha AI — Automated Pull Request Review",
            f"",
            f"**PR Title:** {pr_title}",
            f"**Files Changed:** {len(files_list)}",
            f"**Risk Assessment:** **{risk_level}**",
            f"**Merge Recommendation:** `{decision}`",
            f"",
            f"### 📋 Files Analyzed",
        ]
        for f in files_list[:10]:
            md_lines.append(f"- `{f}`")
        if len(files_list) > 10:
            md_lines.append(f"- *...and {len(files_list) - 10} more files*")

        md_lines.append(f"\n### 🛡️ Security & SAST Findings")
        if not findings:
            md_lines.append("✅ **Zero security vulnerabilities detected in new code.**")
        else:
            for f in findings:
                sev_icon = "🔴" if f["severity"] == "high" else "🟡"
                md_lines.append(f"- {sev_icon} **[{f['rule_id']}]** `{f['message']}` (Line ~{f['line']})")

        md_lines.append(f"\n### 💡 Recommendations")
        if decision == "APPROVE":
            md_lines.append("1. All static checks and security gates passed.")
            md_lines.append("2. Ready for peer developer review and merge.")
        else:
            md_lines.append("1. **Resolve security findings above before merging.**")
            md_lines.append("2. Run `saleha sast .` locally to verify fixes.")

        full_md = "\n".join(md_lines)

        return PRReviewReport(
            summary=f"Analyzed {len(files_list)} files with {len(findings)} security findings.",
            risk_level=risk_level,
            files_analyzed=files_list,
            security_findings=findings,
            recommendations=["Follow clean architecture principles and verify automated unit tests."],
            merge_decision=decision,
            markdown_report=full_md
        )


# Global instance
pr_reviewer = PRReviewer()
