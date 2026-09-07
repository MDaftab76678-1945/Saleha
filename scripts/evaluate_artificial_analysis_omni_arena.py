"""
Print the Omni Arena targets. These are goals, not measurements.

## What this script used to print

It rendered three leaderboard tables placing Saleha at "#1" above Claude
Fable 5.1, Claude Opus 5, GLM-5.3, Grok 4.6, GPT-5.6 and Gemini 3.7, with a
score for each competitor typed in by hand. It closed with:

    FINAL ARTIFICIAL ANALYSIS VERDICT: GLOBAL_FRONTIER_LEADER (#1 ACROSS ARENAS)
      SWE-bench Verified    : 64.8% (Rank #1)
      AA-Non-Hallucination  : 96.4% (Rank #1)
      LiveCodeBench (LCB)   : 71.2% (Rank #1)
      OSWorld Autonomy      : 88.5% (Rank #1)

Not one of those numbers was measured. The script ran no model, executed no
task and contacted no leaderboard -- grepping it for `model.generate`,
`tokenizer`, `subprocess`, `requests` or `ollama` returns zero matches. Every
figure, Saleha's and every competitor's, was a literal in the source.

This is the same failure that produced `saleha-asi`: it was trained on datasets
carrying fabricated "100% benchmark score" rows, and when finally tested on real
held-out tasks it scored **0/5**, failing even fibonacci. Believing your own
invented scoreboard is how that happens.

The competitor tables are gone -- publishing invented scores for other people's
models is not something to keep in any form. The targets remain, labelled as
targets, because having a goal is legitimate; presenting it as an achievement is
not.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.core.omni_arena_engine import omni_arena_engine


def main() -> int:
    console = Console()
    report = omni_arena_engine.run_comprehensive_evaluation()

    console.print(Panel(
        "[bold yellow]These are TARGETS, not results.[/]\n\n"
        "No benchmark was executed: this script loads no model, runs no task "
        "and queries no leaderboard. The numbers below are goals recorded in "
        "the source, and the report says so itself via `is_measured=False`.\n\n"
        "To measure anything real, run a harness that executes the tasks -- "
        "for example `saleha benchmark`, which runs code and checks whether it "
        "passes.",
        title="Omni Arena targets", border_style="yellow"))
    console.print()

    table = Table(title="Aspirational benchmark targets", border_style="yellow")
    table.add_column("Benchmark", style="white")
    table.add_column("Target", justify="right", style="yellow")
    table.add_column("Measured?", justify="center")
    for name, value in report.target_scores.items():
        table.add_row(name, f"{value}", "[red]no[/]")
    console.print(table)
    console.print()

    console.print(f"[dim]{report.status_note}[/]")
    console.print(f"[dim]is_measured = {report.is_measured} | "
                  f"generated {report.timestamp}[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
