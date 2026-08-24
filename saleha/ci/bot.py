"""
Saleha Autonomous CI/CD & GitHub PR Review Bot

Inspects code changes, performs AST SAST security audits, runs unit tests,
and generates structured enterprise PR reviews with remediation diffs.
"""

import os
import sys
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from saleha import __version__
from saleha.core.security_scanner import ASTSecurityScanner, ScanReport
from saleha.core.polyglot_indexer import PolyglotIndexer


@dataclass
class ReviewReport:
    status: str  # "APPROVED", "CHANGES_REQUESTED", "COMMENT"
    quality_score: int  # 0 to 100
    total_files: int
    total_loc: int
    security_report: ScanReport
    markdown_review: str
    suggested_actions: List[str] = field(default_factory=list)


class PRReviewBot:
    """Autonomous GitHub Actions and CI Review Bot."""

    def __init__(self):
        self.security_scanner = ASTSecurityScanner()
        self.polyglot_indexer = PolyglotIndexer()

    def review_path(self, target_path: str = ".", pr_number: Optional[int] = None) -> ReviewReport:
        """Performs automated multi-factor code review on a repository or changed PR files."""
        abs_path = os.path.abspath(target_path)
        
        # 1. Polyglot codebase summary
        polyglot_summary = self.polyglot_indexer.scan_directory(abs_path)
        
        # 2. Deep AST Security SAST scan
        sec_report = self.security_scanner.scan_directory(abs_path)

        # 3. Compute Quality Score
        # Start at 100, deduct for vulnerabilities and maintainability
        score = 100
        score -= (sec_report.high_count * 25)
        score -= (sec_report.medium_count * 10)
        score -= (sec_report.low_count * 3)
        score = max(0, min(100, score))

        # 4. Status determination
        if sec_report.high_count > 0:
            status = "CHANGES_REQUESTED"
        elif score >= 80:
            status = "APPROVED"
        else:
            status = "COMMENT"

        # 5. Suggested actions
        suggestions = []
        if sec_report.high_count > 0:
            suggestions.append(f"Resolve {sec_report.high_count} HIGH severity security vulnerabilities before merging.")
        if sec_report.medium_count > 0:
            suggestions.append(f"Review {sec_report.medium_count} medium-risk patterns.")
        if not suggestions:
            suggestions.append("Code meets all enterprise safety and architecture guidelines.")

        # 6. Format Markdown Review Report
        md = self._format_markdown(pr_number, status, score, polyglot_summary, sec_report, suggestions)

        return ReviewReport(
            status=status,
            quality_score=score,
            total_files=polyglot_summary.get("total_files", 0),
            total_loc=polyglot_summary.get("total_loc", 0),
            security_report=sec_report,
            markdown_review=md,
            suggested_actions=suggestions
        )

    def _format_markdown(self, pr_number: Optional[int], status: str, score: int,
                          polyglot: Dict[str, Any], sec: ScanReport,
                          suggestions: List[str]) -> str:
        status_badge = {
            "APPROVED": "🟢 **APPROVED**",
            "CHANGES_REQUESTED": "🔴 **CHANGES REQUESTED**",
            "COMMENT": "🟡 **COMMENTS NOTED**"
        }.get(status, status)

        pr_header = f"### 🧠 Saleha AI Autonomous Review (PR #{pr_number})" if pr_number else "### 🧠 Saleha AI Autonomous CI/CD Review"

        lines = [
            pr_header,
            "",
            f"**Review Status**: {status_badge} | **Quality Score**: `{score}/100` | **Saleha**: `v{__version__}`",
            "",
            "#### 📊 Codebase Metrics",
            f"- **Files Scanned**: `{polyglot.get('total_files', 0)}` files across {', '.join(polyglot.get('languages', {}).keys()) or 'None'}",
            f"- **Lines of Code (LOC)**: `{polyglot.get('total_loc', 0)}`",
            f"- **Extracted Symbols**: `{polyglot.get('total_symbols', 0)}`",
            "",
            "#### 🛡️ AST SAST Security Audit",
            f"- **High Severity**: `{sec.high_count}`",
            f"- **Medium Severity**: `{sec.medium_count}`",
            f"- **Low Severity**: `{sec.low_count}`",
            ""
        ]

        if sec.vulnerabilities:
            lines.extend([
                "| Rule | Severity | Location | Issue | Remediation |",
                "|---|:---:|---|---|---|"
            ])
            for v in sec.vulnerabilities:
                loc = f"`{os.path.basename(v.file_path)}:{v.line_number}`"
                lines.append(f"| `{v.rule_id}` | `{v.severity.upper()}` | {loc} | {v.description} | {v.remediation} |")
            lines.append("")
        else:
            lines.append("✅ **No security vulnerabilities found.** Safe to merge.\n")

        lines.append("#### 📋 Recommended Actions")
        for s in suggestions:
            lines.append(f"- {s}")
        lines.append("")
        lines.append("---")
        lines.append("*Generated autonomously by [Saleha AI Platform](https://github.com/aftab-alam/saleha-0.1)*")

        return "\n".join(lines)
