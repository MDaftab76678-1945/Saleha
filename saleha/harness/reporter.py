"""
Saleha Harness: Interactive Leaderboard & Comprehensive Report Generator

Renders rich terminal leaderboards, tracks model ranking histories, and exports
professional Markdown and HTML benchmark reports.
"""

import os
import json
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.harness.metrics import BenchmarkSummary, HarnessTaskResult

console = Console()
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".saleha", "harness_history.json")


@dataclass
class HarnessReport:
    model_name: str
    timestamp: str
    total_tasks: int
    overall_pass_at_1: float
    overall_pass_at_5: float
    avg_latency_sec: float
    avg_tokens_per_sec: float
    benchmark_summaries: Dict[str, BenchmarkSummary] = field(default_factory=dict)


class HarnessReporter:
    """Generates leaderboards and exports evaluation reports."""

    def __init__(self, history_path: str = HISTORY_FILE):
        self.history_path = history_path

    def save_report(self, report: HarnessReport) -> bool:
        """Saves evaluation run to persistent history JSON."""
        history = self.load_history()
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        
        record = {
            "model": report.model_name,
            "timestamp": report.timestamp,
            "total_tasks": report.total_tasks,
            "pass_at_1": report.overall_pass_at_1,
            "pass_at_5": report.overall_pass_at_5,
            "avg_latency": report.avg_latency_sec,
            "avg_tok_sec": report.avg_tokens_per_sec,
            "benchmarks": {
                k: {
                    "total": v.total_tasks,
                    "passed": v.passed_tasks,
                    "pass_at_1": v.pass_at_1,
                    "latency": v.avg_latency_sec
                } for k, v in report.benchmark_summaries.items()
            }
        }
        history.append(record)
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
            return True
        except OSError:
            return False

    def load_history(self) -> List[Dict[str, Any]]:
        """Loads historical benchmark records."""
        if not os.path.isfile(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def render_leaderboard(self):
        """Displays ranked model leaderboard in terminal."""
        history = self.load_history()
        if not history:
            console.print("[yellow]No harness benchmark records found. Run 'saleha harness run' first.[/]")
            return

        # Sort by pass_at_1 descending, then latency ascending
        ranked = sorted(history, key=lambda x: (-x.get("pass_at_1", 0), x.get("avg_latency", 999)))

        table = Table(title="🏆 Saleha Model Evaluation Leaderboard (DeepSeek-Standard)", border_style="green")
        table.add_column("Rank", justify="center", style="bold")
        table.add_column("Model Name", style="bold cyan")
        table.add_column("Pass@1", justify="right", style="bold green")
        table.add_column("Pass@5", justify="right", style="green")
        table.add_column("Avg Latency", justify="right", style="yellow")
        table.add_column("Tok / Sec", justify="right", style="cyan")
        table.add_column("Evaluated At", style="dim")

        for idx, rec in enumerate(ranked, 1):
            rank_icon = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"{idx}"))
            table.add_row(
                rank_icon,
                rec.get("model", "unknown"),
                f"{rec.get('pass_at_1', 0.0)}%",
                f"{rec.get('pass_at_5', 0.0)}%",
                f"{rec.get('avg_latency', 0.0)}s",
                f"{rec.get('avg_tok_sec', 0.0)}",
                rec.get("timestamp", "-")[:16]
            )

        console.print(table)

    def export_markdown(self, report: HarnessReport, filepath: str) -> bool:
        """Exports evaluation results to clean GitHub Markdown format."""
        md = [
            f"# 🧪 Saleha Harness Evaluation Report",
            f"",
            f"**Model Evaluated:** `{report.model_name}`  ",
            f"**Evaluation Timestamp:** `{report.timestamp}`  ",
            f"**Overall Pass@1 Accuracy:** **{report.overall_pass_at_1}%**  ",
            f"**Unbiased Pass@5 Estimate:** **{report.overall_pass_at_5}%**  ",
            f"**Average Latency:** `{report.avg_latency_sec}s / task`  ",
            f"",
            f"## 📊 Benchmark Suite Breakdown",
            f"",
            f"| Benchmark Suite | Total Tasks | Passed | Pass@1 Rate | Avg Latency |",
            f"|---|:---:|:---:|:---:|:---:|",
        ]

        for name, summ in report.benchmark_summaries.items():
            md.append(f"| `{name}` | {summ.total_tasks} | {summ.passed_tasks} | **{summ.pass_at_1}%** | {summ.avg_latency_sec}s |")

        md.append("\n## 📋 Task Details\n")
        for name, summ in report.benchmark_summaries.items():
            md.append(f"### Benchmark: `{name}`")
            for t in summ.task_results:
                icon = "✅" if t.passed else "❌"
                md.append(f"- {icon} **[{t.task_id}]** (Latency: {t.latency_sec}s, Attempts: {t.attempts_used})")

        content = "\n".join(md)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except OSError:
            return False


# Global instance
reporter = HarnessReporter()

