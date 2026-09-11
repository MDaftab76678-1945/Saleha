"""
Saleha: GRPO Group-Relative Reward Scoring Run

Runs real group rollouts (G candidates per prompt, each a genuine model
call via CoderAgent) and scores them with the real AST security scanner
and neuro-symbolic invariant scorer, then reports group-relative advantage.

This does not train or deploy a model -- see
saleha/core/grpo_reasoning_trainer.py for what is and is not implemented.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.core.grpo_reasoning_trainer import GRPOReasoningTrainer


def main():
    console = Console()
    console.print("\n" + "=" * 75, style="bold magenta")
    console.print("[bold white on magenta] SALEHA GRPO GROUP-RELATIVE REWARD SCORING [/]", justify="center")
    console.print("=" * 75, style="bold magenta")
    console.print("[dim]Real per-rollout model calls, real AST/security scoring, no training[/dim]\n")

    trainer = GRPOReasoningTrainer(group_size=4)
    summary = trainer.run_full_grpo_training(target_steps=3)

    console.print(f"\n[bold green]Scoring run complete in {summary.training_duration_sec}s "
                  f"({summary.total_rollouts} real rollouts across {summary.total_steps} prompts)[/bold green]\n")
    console.print(f"[dim]{summary.note}[/dim]\n")

    for step_res in summary.steps:
        table = Table(
            title=f"Step {step_res.step}: {step_res.prompt}",
            border_style="cyan",
        )
        table.add_column("Rollout", style="white", justify="center")
        table.add_column("Model", style="dim")
        table.add_column("Generated", style="bold", justify="center")
        table.add_column("AST Valid", style="bold green", justify="center")
        table.add_column("Unresolved HIGH", style="yellow", justify="center")
        table.add_column("Reward (R_i)", style="cyan", justify="center")
        table.add_column("Advantage (A_i)", style="bold magenta", justify="center")

        for r in step_res.rollouts:
            adv_str = f"+{r.normalized_advantage:.2f}" if r.normalized_advantage >= 0 else f"{r.normalized_advantage:.2f}"
            table.add_row(
                r.rollout_id,
                r.model_used or "?",
                "yes" if r.generation_succeeded else "no",
                "yes" if r.ast_valid else "no",
                str(r.security_findings_unresolved),
                f"{r.total_reward:.4f}",
                f"[bold green]{adv_str}[/]" if r.normalized_advantage > 0 else f"[red]{adv_str}[/]",
            )
        console.print(table)

    summary_text = (
        f"[bold]Steps run:[/] {summary.total_steps}\n"
        f"[bold]Total real rollouts:[/] {summary.total_rollouts}\n"
        f"[bold]Mean reward:[/] step 1 = {summary.initial_mean_reward} -> "
        f"final step = {summary.final_mean_reward}\n\n"
        f"[dim]{summary.note}[/dim]"
    )
    console.print(Panel(summary_text, title="Group-Relative Reward Summary", border_style="magenta"))


if __name__ == "__main__":
    main()
