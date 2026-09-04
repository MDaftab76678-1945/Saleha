# k8s/chaos/orchestrator/report.py
"""
Generate chaos report as JSON + Markdown for documentation.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from chaos_runner import ExperimentResult


def save_json_report(results: List[ExperimentResult], path: str = "chaos-report.json") -> None:
    """Save results as JSON."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_experiments": len(results),
        "passed": sum(1 for r in results if r.overall_passed),
        "failed": sum(1 for r in results if not r.overall_passed),
        "results": [asdict(r) for r in results],
    }
    Path(path).write_text(json.dumps(report, indent=2, default=str))


def save_markdown_report(results: List[ExperimentResult], path: str = "chaos-report.md") -> None:
    """Save results as Markdown (for runbook documentation)."""
    lines = [
        "# Chaos Engineering Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"- **Total experiments:** {len(results)}",
        f"- **Passed:** {sum(1 for r in results if r.overall_passed)}",
        f"- **Failed:** {sum(1 for r in results if not r.overall_passed)}",
        "",
        "## Results",
        "",
        "| Experiment | Runbook | Baseline | Recovery | Recovery Time | Verdict |",
        "|------------|---------|----------|----------|---------------|---------|",
    ]

    for r in results:
        baseline = "✅" if r.baseline_passed else "❌"
        recovery = "✅" if r.recovery_passed else "❌"
        verdict = "✅ PASS" if r.overall_passed else "❌ FAIL"
        rec_time = f"{r.recovery_time_seconds:.1f}s"
        lines.append(
            f"| {r.name} | {r.runbook_ref} | {baseline} | {recovery} | {rec_time} | {verdict} |"
        )

    lines += ["", "## Hypotheses", ""]
    for r in results:
        lines.append(f"### {r.name} ({r.runbook_ref})")
        lines.append(f"- **Hypothesis:** {r.hypothesis}")
        lines.append(f"- **Verdict:** {'Validated ✅' if r.overall_passed else 'NOT validated ❌'}")
        if r.error:
            lines.append(f"- **Error:** {r.error}")
        lines.append("")

    Path(path).write_text("\n".join(lines))
