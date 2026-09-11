"""
Saleha: Swarm Self-Play Arena Scoring Run

Runs the 4-tier curriculum through the real adversarial scoring loop:
each task prompt gets one real CoderAgent-generated candidate, attacked by
the real AST security scanner and scored by the real neuro-symbolic
invariant/fuzz scorers. See saleha/core/swarm_self_play_arena.py for what
this module does and does not do -- it does not train weights or perform
weight averaging.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.core.swarm_self_play_arena import SwarmSelfPlayArena, RoundReward


def main():
    console = Console()
    console.print("\n" + "=" * 80, style="bold red")
    console.print("[bold white on red] SALEHA ADVERSARIAL SWARM SELF-PLAY ARENA [/]", justify="center")
    console.print("=" * 80, style="bold red")
    console.print("[dim]Real per-round CoderAgent generation, real AST/security/fuzz scoring[/dim]\n")

    arena = SwarmSelfPlayArena()

    battles = []
    b_idx = 1
    for level in range(1, 5):
        for prompt in arena.curriculum.get_tier_prompts(level):
            console.print(f"[cyan]Level {level}[/]: {prompt}")
            result = arena.fight_battle(b_idx, level, prompt)
            battles.append(result)
            arena.aggregator.add_round(
                RoundReward(
                    round_id=f"round_lvl_{level}_b_{b_idx}",
                    step=b_idx,
                    reward_score=round(result.judge_pareto_reward * 100, 2),
                )
            )
            b_idx += 1

    aggregate = arena.aggregator.aggregate()

    table = Table(title="Adversarial Arena Battle Log (real per-round results)", border_style="red")
    table.add_column("Battle", style="bold", justify="center")
    table.add_column("Level", style="white", justify="center")
    table.add_column("Coder Model", style="dim")
    table.add_column("Generated", style="bold", justify="center")
    table.add_column("Unresolved HIGH", style="red", justify="center")
    table.add_column("Fuzz Resilience", style="bold green", justify="center")
    table.add_column("Pareto Reward", style="bold cyan", justify="center")
    table.add_column("Hard Negative", style="yellow", justify="center")

    for b in battles:
        table.add_row(
            b.battle_id,
            str(b.curriculum_level),
            b.coder_model_used or "?",
            "yes" if b.coder_succeeded else "no",
            str(b.security_findings_unresolved),
            f"{b.chaos_resilience_pct:.1f}%",
            f"{b.judge_pareto_reward:.4f}",
            "yes" if b.hard_negative_mined else "no",
        )

    console.print(table)
    console.print()

    total_attacks_through = sum(b.security_findings_unresolved for b in battles)
    hard_negatives = sum(1 for b in battles if b.hard_negative_mined)

    summary_text = (
        f"[bold]Battles fought:[/] {len(battles)}\n"
        f"[bold]Attacks that got through (unresolved HIGH findings):[/] {total_attacks_through}\n"
        f"[bold]Hard negatives mined:[/] {hard_negatives}\n"
        f"[bold]Aggregate reward (top-{arena.aggregator.top_k} mean):[/] "
        f"{aggregate.get('aggregate_reward_score', 0.0)}\n\n"
        f"[dim]No weight averaging or training happens here -- this is a scoring "
        f"run over real generated candidates. See module docstring.[/dim]"
    )
    console.print(Panel(summary_text, title="Self-Play Arena Summary", border_style="magenta"))


if __name__ == "__main__":
    main()
