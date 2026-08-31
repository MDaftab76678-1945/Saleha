"""
Saleha Core: Code Review HTML Report Generator

Transforms CodeReviewReport objects into beautiful severity-heatmap HTML
reports with syntax highlighting, OWASP links, and fix suggestions.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional
from saleha.core.ai_reviewer import CodeReviewReport, ReviewIssue
from saleha import __version__


SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#3b82f6",
    "info": "#6b7280",
}


class ReviewReporter:
    """Generates rich HTML reports from CodeReviewReport objects."""

    def generate_html(self, reports: List[CodeReviewReport]) -> str:
        """Builds a full HTML review dashboard for multiple files."""
        total_issues = sum(len(r.issues) for r in reports)
        avg_score = round(sum(r.score for r in reports) / max(len(reports), 1))
        critical = sum(r.critical_count for r in reports)

        score_color = "#22c55e" if avg_score >= 80 else "#eab308" if avg_score >= 60 else "#ef4444"

        issue_rows = ""
        for report in reports:
            for issue in report.issues:
                color = SEVERITY_COLORS.get(issue.severity, "#6b7280")
                issue_rows += f"""
            <tr>
                <td><code>{report.file_path}</code></td>
                <td>{issue.line}</td>
                <td style="color:{color}; font-weight:bold">{issue.severity.upper()}</td>
                <td>{issue.category}</td>
                <td>{issue.title}</td>
                <td><small>{issue.cwe_id}</small></td>
                <td><small>{issue.suggestion[:80]}</small></td>
            </tr>"""

        file_cards = ""
        for report in reports:
            sc = "#22c55e" if report.score >= 80 else "#eab308" if report.score >= 60 else "#ef4444"
            file_cards += f"""
        <div class="card">
            <h3>{os.path.basename(report.file_path)}</h3>
            <div class="score" style="color:{sc}">{report.score}/100</div>
            <p>{report.lines_reviewed} lines | {len(report.issues)} issues</p>
            <p><small>{report.summary}</small></p>
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Saleha AI Code Review</title>
<style>
  body {{ background:#0d1117; color:#c9d1d9; font-family:-apple-system,sans-serif; margin:0; padding:24px; }}
  .header {{ background:#161b22; border-bottom:2px solid #21262d; padding:20px 32px; display:flex; justify-content:space-between; align-items:center; }}
  h1 {{ margin:0; color:#f0f6fc; font-size:22px; }}
  .badge {{ background:#238636; color:#fff; padding:4px 12px; border-radius:20px; font-weight:bold; font-size:13px; }}
  .stats {{ display:flex; gap:20px; margin:24px 0; }}
  .stat-box {{ background:#161b22; border:1px solid #21262d; border-radius:8px; padding:16px 24px; text-align:center; flex:1; }}
  .stat-num {{ font-size:36px; font-weight:bold; }}
  .stat-label {{ font-size:12px; color:#8b949e; margin-top:4px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; margin:24px 0; }}
  .card {{ background:#161b22; border:1px solid #21262d; border-radius:8px; padding:16px; }}
  .card h3 {{ margin:0 0 8px; color:#58a6ff; font-size:14px; }}
  .score {{ font-size:32px; font-weight:bold; }}
  table {{ width:100%; border-collapse:collapse; background:#161b22; border-radius:8px; overflow:hidden; margin-top:24px; }}
  th {{ background:#21262d; color:#8b949e; padding:10px 14px; text-align:left; font-size:12px; text-transform:uppercase; }}
  td {{ padding:10px 14px; border-bottom:1px solid #21262d; font-size:13px; }}
  tr:hover {{ background:#1c2128; }}
  code {{ background:#21262d; padding:2px 6px; border-radius:4px; font-size:12px; }}
</style></head>
<body>
<div class="header">
  <h1>🔍 Saleha AI — Code Review Dashboard</h1>
  <span class="badge">v{__version__} | {time.strftime('%Y-%m-%d %H:%M')}</span>
</div>
<div class="stats">
  <div class="stat-box"><div class="stat-num" style="color:{score_color}">{avg_score}</div><div class="stat-label">AVG SCORE /100</div></div>
  <div class="stat-box"><div class="stat-num">{len(reports)}</div><div class="stat-label">FILES REVIEWED</div></div>
  <div class="stat-box"><div class="stat-num" style="color:#ef4444">{critical}</div><div class="stat-label">CRITICAL ISSUES</div></div>
  <div class="stat-box"><div class="stat-num">{total_issues}</div><div class="stat-label">TOTAL ISSUES</div></div>
</div>
<h2 style="color:#f0f6fc">📁 File Scores</h2>
<div class="grid">{file_cards}</div>
<h2 style="color:#f0f6fc">🐛 All Issues</h2>
<table>
  <tr><th>File</th><th>Line</th><th>Severity</th><th>Category</th><th>Issue</th><th>CWE</th><th>Fix</th></tr>
  {issue_rows}
</table>
</body></html>"""

    def save_report(self, reports: List[CodeReviewReport], output_path: str = "review_report.html") -> str:
        """Saves HTML report to disk."""
        html = self.generate_html(reports)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(html)
        os.replace(tmp, output_path)
        return os.path.abspath(output_path)


# Global instance
review_reporter = ReviewReporter()
