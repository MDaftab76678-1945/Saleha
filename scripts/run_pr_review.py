"""
Entry point for the `Saleha AI Autonomous Code Reviewer` GitHub Action
(action.yml). Kept as a real file rather than an inline `python -c` block:
the previous inline version imported names that do not exist -- `AIReviewer`
(the class is `AICodeReviewer`), `Severity`, `review_workspace`,
`WorkspaceReviewReport`, `ReviewReporter.render_markdown` -- so the Action
failed at import on every run and never once produced a review.

This walks the scan path, runs the real `AICodeReviewer.review_file` on each
Python file, writes `saleha_review.md` for the PR comment step, appends the
same summary to the workflow run summary, and exits non-zero only when
`fail-on-critical` is set and a critical/high issue was found.
"""

from __future__ import annotations

import os
import sys

from saleha.core.ai_reviewer import AICodeReviewer, CodeReviewReport

_SKIP_DIRS = {"__pycache__", ".git", ".venv", ".venv_train", "node_modules", "dist", "build"}


def _iter_python_files(target: str):
    if os.path.isfile(target):
        if target.endswith(".py"):
            yield target
        return
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def _review(target: str) -> list[CodeReviewReport]:
    reviewer = AICodeReviewer()
    reports: list[CodeReviewReport] = []
    for path in _iter_python_files(target):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            print(f"skip {path}: {exc}")
            continue
        reports.append(reviewer.review_file(path, content))
    return reports


def _render_markdown(reports: list[CodeReviewReport], base: str) -> str:
    total_issues = sum(len(r.issues) for r in reports)
    total_critical = sum(r.critical_count for r in reports)
    total_high = sum(r.high_count for r in reports)
    avg = round(sum(r.score for r in reports) / len(reports)) if reports else 100

    lines = [
        "# Saleha AI Code Review",
        "",
        f"- Files reviewed: **{len(reports)}**",
        f"- Average score: **{avg}/100**",
        f"- Issues: **{total_issues}** ({total_critical} critical, {total_high} high)",
        "",
    ]
    flagged = [r for r in reports if r.issues]
    if not flagged:
        lines.append("No issues found in the scanned files.")
        return "\n".join(lines)

    flagged.sort(key=lambda r: r.score)
    for report in flagged:
        rel = os.path.relpath(report.file_path, base) if os.path.isdir(base) else report.file_path
        lines.append(f"## `{rel}` -- {report.score}/100")
        for issue in report.issues:
            cwe = f" ({issue.cwe_id})" if issue.cwe_id else ""
            lines.append(
                f"- **[{issue.severity.upper()}]** line {issue.line}: "
                f"{issue.title}{cwe} -- {issue.suggestion}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    target = os.environ.get("SALEHA_SCAN_PATH", ".")
    fail_on_critical = os.environ.get("SALEHA_FAIL_ON_CRITICAL", "true").lower() == "true"

    if not os.path.exists(target):
        print(f"::error title=Saleha review::scan path not found: {target}")
        return 1

    reports = _review(target)
    if not reports:
        print(f"No Python files found under {target}; nothing to review.")
        return 0

    markdown = _render_markdown(reports, target)
    print(markdown)

    with open("saleha_review.md", "w", encoding="utf-8") as fh:
        fh.write(markdown)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")

    has_critical = any(r.critical_count or r.high_count for r in reports)
    if fail_on_critical and has_critical:
        print(
            "::error title=Security Vulnerability::"
            "Saleha found critical or high severity issues in the reviewed files."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
