"""
Saleha Harness: Leaderboard & Report Generator

Keeps the persistent run history, renders the terminal leaderboard, and exports
Markdown reports.

Only runs in which at least one task actually executed are recorded (see
`core.SalehaHarness.evaluate`), and `save_report` refuses dry runs outright. A
history file that cannot be parsed is moved aside, never overwritten: the old
behaviour read it as empty and the next save replaced every record in it.

No emoji anywhere in this module's output: the leaderboard crashed with
UnicodeEncodeError on this machine's cp1252 console.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from saleha.harness.metrics import BenchmarkSummary

console = Console()
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".saleha", "harness_history.json")


@dataclass
class HarnessReport:
    model_name: str
    timestamp: str
    total_tasks: int
    executed_tasks: int
    passed_tasks: int
    overall_pass_at_1: Optional[float]  # None when no task executed
    avg_latency_sec: float
    benchmark_summaries: Dict[str, BenchmarkSummary] = field(default_factory=dict)
    dry_run: bool = False
    planned_tasks: Dict[str, List[str]] = field(default_factory=dict)
    saved: bool = False


def _fmt_pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value}%"


class HarnessReporter:
    """Generates leaderboards and exports evaluation reports."""

    def __init__(self, history_path: str = HISTORY_FILE):
        self.history_path = history_path

    def _read_history(self) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Return (records, problem). `problem` is set when the file exists but is unusable."""
        if not os.path.isfile(self.history_path):
            return [], None
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            return [], f"{type(e).__name__}: {e}"
        if not isinstance(data, list):
            return [], f"expected a JSON list, found {type(data).__name__}"
        return data, None

    def save_report(self, report: HarnessReport) -> bool:
        """Appends a run to the persistent history. Refuses runs that measured nothing."""
        if report.dry_run or report.executed_tasks <= 0 or report.overall_pass_at_1 is None:
            return False

        history, problem = self._read_history()
        try:
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            if problem is not None:
                # Keep the unreadable file for inspection instead of replacing it.
                os.replace(self.history_path, f"{self.history_path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        except OSError:
            return False

        history.append({
            "model": report.model_name,
            "timestamp": report.timestamp,
            "total_tasks": report.total_tasks,
            "executed_tasks": report.executed_tasks,
            "passed_tasks": report.passed_tasks,
            "pass_at_1": report.overall_pass_at_1,
            "avg_latency": report.avg_latency_sec,
            "benchmarks": {
                k: {
                    "total": v.total_tasks,
                    "executed": v.executed_tasks,
                    "passed": v.passed_tasks,
                    "pass_at_1": v.pass_at_1,
                    "latency": v.avg_latency_sec,
                } for k, v in report.benchmark_summaries.items()
            },
        })
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
            return True
        except OSError:
            return False

    def load_history(self) -> List[Dict[str, Any]]:
        """Loads historical benchmark records ([] if missing or unreadable)."""
        return self._read_history()[0]

    def render_leaderboard(self):
        """Displays ranked model leaderboard in terminal."""
        history, problem = self._read_history()
        if problem is not None:
            console.print(f"[red]Harness history at {self.history_path} is unreadable ({problem}).[/]")
            return
        if not history:
            console.print("[yellow]No harness benchmark records found. Run 'saleha harness run' first.[/]")
            return

        # Rate first; on equal rates the run with more executed tasks ranks higher.
        ranked = sorted(history, key=lambda x: (-(x.get("pass_at_1") or 0.0),
                                                -(x.get("executed_tasks") or 0),
                                                x.get("avg_latency", 999)))

        table = Table(title="Saleha Model Evaluation Leaderboard (Pass@1, one sample per task)",
                      border_style="green")
        table.add_column("Rank", justify="center", style="bold")
        table.add_column("Model Name", style="bold cyan")
        table.add_column("Pass@1", justify="right", style="bold green")
        table.add_column("Passed / Executed", justify="right", style="green")
        table.add_column("Not Run", justify="right")
        table.add_column("Avg Latency", justify="right", style="yellow")
        table.add_column("Evaluated At", style="dim")

        for idx, rec in enumerate(ranked, 1):
            executed = rec.get("executed_tasks")
            total = rec.get("total_tasks")
            not_run = "-" if executed is None or total is None else str(total - executed)
            table.add_row(
                str(idx),
                str(rec.get("model", "unknown")),
                _fmt_pct(rec.get("pass_at_1")),
                f"{rec.get('passed_tasks', '?')} / {executed if executed is not None else '?'}",
                not_run,
                f"{rec.get('avg_latency', 0.0)}s",
                str(rec.get("timestamp") or "-")[:16],
            )

        console.print(table)

    def export_markdown(self, report: HarnessReport, filepath: str) -> bool:
        """Exports evaluation results to GitHub Markdown."""
        md = [
            "# Saleha Harness Evaluation Report",
            "",
            f"**Model Evaluated:** `{report.model_name}`  ",
            f"**Evaluation Timestamp:** `{report.timestamp}`  ",
        ]
        if report.dry_run:
            md += ["", "**Dry run: nothing was generated or executed. There is no score.**", "",
                   "## Planned Tasks", ""]
            for name, ids in report.planned_tasks.items():
                md.append(f"- `{name}`: {', '.join(ids)}")
        else:
            md += [
                f"**Pass@1 (executed tasks):** **{_fmt_pct(report.overall_pass_at_1)}**  ",
                f"**Passed / Executed / Total:** {report.passed_tasks} / {report.executed_tasks} / {report.total_tasks}  ",
                f"**Average Latency:** `{report.avg_latency_sec}s / executed task`  ",
                "",
                "## Benchmark Suite Breakdown",
                "",
                "| Benchmark Suite | Total | Executed | Passed | Pass@1 | Avg Latency |",
                "|---|:---:|:---:|:---:|:---:|:---:|",
            ]
            for name, summ in report.benchmark_summaries.items():
                md.append(f"| `{name}` | {summ.total_tasks} | {summ.executed_tasks} | {summ.passed_tasks} "
                          f"| **{_fmt_pct(summ.pass_at_1)}** | {summ.avg_latency_sec}s |")

            md.append("\n## Task Details\n")
            for name, summ in report.benchmark_summaries.items():
                md.append(f"### Benchmark: `{name}`")
                for t in summ.task_results:
                    verdict = "PASS" if t.passed else ("NOT RUN" if not t.executed else "FAIL")
                    # The last line of a traceback names the exception; the first is boilerplate.
                    detail_lines = [ln for ln in (t.error_detail or "").splitlines() if ln.strip()]
                    why = f" -- {detail_lines[-1].strip()[:160]}" if detail_lines else ""
                    md.append(f"- {verdict} **[{t.task_id}]** (Latency: {t.latency_sec}s, "
                              f"Attempts: {t.attempts_used}){why}")

        content = "\n".join(md) + "\n"
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except OSError:
            return False


# Global instance
reporter = HarnessReporter()
