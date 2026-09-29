"""CLI: `saleha align` -- Frontier Post-Training Alignment & PRM Compute Scaling.

Provides commands to:
1. Verify code against physical hardware & SMT contracts (RLHVR).
2. Audit constitutional AI rubrics (RLAIF).
3. Decompose code into steps and score via Process Reward Model (PRM).
4. Generate contrastive dialogue pairs (RLCD).
5. Compile and export Direct Preference Optimization (DPO) datasets.
6. Check preference store stats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
from rich.table import Table

from saleha.cli.commands import cli, console


@cli.group("align")
def align_group() -> None:
    """Post-Training Alignment, RLHVR, PRM & DPO Engine."""


@align_group.command("status")
def align_status_cmd() -> None:
    """Displays physical alignment store metrics and contrastive dataset stats."""
    from saleha.core.alignment.preference_store import RLHFStore

    store = RLHFStore()
    summary = store.get_summary()

    table = Table(title="Saleha Frontier Alignment Preference Store", safe_box=True)
    table.add_column("Metric", style="cyan bold")
    table.add_column("Value", justify="right", style="bold")

    table.add_row("Total Human Feedback", str(summary["total_feedback_entries"]))
    table.add_row("Positive (Thumbs Up)", f"[green]{summary['positive_feedback_count']}[/green]")
    table.add_row("Negative (Thumbs Down)", f"[red]{summary['negative_feedback_count']}[/red]")
    table.add_row("Avg Human Rating", f"{summary['average_human_rating']:+.3f}")
    table.add_row("Stored Contrastive Pairs", str(summary["total_contrastive_pairs"]))
    table.add_row("Database Path", summary["db_path"])

    console.print(table)


@align_group.command("rlhvr")
@click.argument("code_file", type=click.Path(exists=True))
@click.option("--test", "test_file", type=click.Path(exists=True), default=None, help="Optional test file to execute in sandbox.")
def align_rlhvr_cmd(code_file: str, test_file: Optional[str]) -> None:
    """Evaluates code physically against Win32 Job Object sandbox, AST, and Z3 SMT contracts."""
    from saleha.core.alignment.verifiable_rewards import RLHVRVerifier

    code = Path(code_file).read_text(encoding="utf-8")
    test_code = Path(test_file).read_text(encoding="utf-8") if test_file else None

    verifier = RLHVRVerifier()
    console.print(f"[bold cyan]Evaluating physical verifiable reward for:[/] {code_file}")
    sig = verifier.verify_code(code, test_code=test_code)

    table = Table(title="RLHVR Physical Reward Verification", safe_box=True)
    table.add_column("Check / Metric", style="cyan bold")
    table.add_column("Result", justify="right")

    hw_color = "green" if sig.hardware_reward > 0 else "red"
    table.add_row("Hardware Reward (RLHVR)", f"[{hw_color}]{sig.hardware_reward:+.3f}[/]")
    table.add_row("AI Rubric Reward (RLAIF)", f"{sig.ai_feedback_reward:.3f}")
    table.add_row("Composite Alignment Score", f"[{hw_color}]{sig.composite_score:+.3f}[/]")
    table.add_row("Sandbox Tests Passed", "[green]YES[/green]" if sig.passed_tests else "[red]NO[/red]")
    table.add_row("AST Syntax Valid", "[green]YES[/green]" if sig.ast_valid else "[red]NO[/red]")
    table.add_row("SMT Formal Contract", "[green]VERIFIED[/green]" if sig.smt_verified else "[yellow]UNVERIFIED[/yellow]")
    table.add_row("Security Clean", "[green]YES[/green]" if sig.security_clean else "[red]VIOLATION[/red]")
    table.add_row("Execution Time", f"{sig.execution_time_ms:.2f} ms")
    table.add_row("Memory Limit Hit", "[red]YES[/red]" if sig.memory_limit_hit else "[green]NO[/green]")

    console.print(table)


@align_group.command("rlaif")
@click.argument("code_file", type=click.Path(exists=True))
def align_rlaif_cmd(code_file: str) -> None:
    """Audits constitutional code rubrics: security, typing, complexity, and defensive structure."""
    from saleha.core.alignment.verifiable_rewards import RLAIFAuditor

    code = Path(code_file).read_text(encoding="utf-8")
    auditor = RLAIFAuditor()
    rubric = auditor.audit_code(code)

    table = Table(title="RLAIF Constitutional AI Rubrics", safe_box=True)
    table.add_column("Constitutional Dimension", style="cyan bold")
    table.add_column("Score (0.0 to 1.0)", justify="right", style="bold")

    table.add_row("Security Posture", f"{rubric['security_score']:.2f}")
    table.add_row("Type Coverage", f"{rubric['type_coverage']:.2f}")
    table.add_row("Cyclomatic Simplicity", f"{rubric['complexity_score']:.2f}")
    table.add_row("Defensive Guarding", f"{rubric['defensive_score']:.2f}")
    table.add_row("Composite AI Rubric", f"[green]{rubric['composite_score']:.3f}[/green]")

    console.print(table)


@align_group.command("prm")
@click.argument("code_file", type=click.Path(exists=True))
def align_prm_cmd(code_file: str) -> None:
    """Decomposes code into logical steps and scores each with the Process Reward Model."""
    from saleha.core.prm_mcts_engine import ProcessRewardModel

    code = Path(code_file).read_text(encoding="utf-8")
    prm = ProcessRewardModel()
    steps = prm.decompose_code_to_steps(code)

    table = Table(title=f"Process Reward Model Step Breakdown: {code_file}", safe_box=True)
    table.add_column("Step", justify="center", style="cyan bold")
    table.add_column("Type", style="bold")
    table.add_column("PRM Score", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Diagnostics", style="dim")

    for s in steps:
        score_color = "green" if s.prm_score >= 0.7 else "yellow" if s.prm_score >= 0.4 else "red"
        status_text = "[green]VALID[/green]" if s.is_valid else "[red]PRUNED[/red]"
        diag_text = "; ".join(s.diagnostics) if s.diagnostics else "None"
        table.add_row(
            str(s.step_index),
            s.step_type,
            f"[{score_color}]{s.prm_score:.3f}[/]",
            status_text,
            diag_text,
        )

    console.print(table)


@align_group.command("rlcd")
@click.argument("code_file", type=click.Path(exists=True))
@click.option("--prompt", required=True, help="Task description prompt.")
@click.option("--test", "test_file", type=click.Path(exists=True), default=None, help="Optional verification test.")
def align_rlcd_cmd(code_file: str, prompt: str, test_file: Optional[str]) -> None:
    """Generates and verifies contrastive critique-revision pairs from code."""
    from saleha.core.alignment.contrastive_rlcd import RLCDGenerator
    from saleha.core.alignment.preference_store import RLHFStore

    code = Path(code_file).read_text(encoding="utf-8")
    test_code = Path(test_file).read_text(encoding="utf-8") if test_file else None

    generator = RLCDGenerator()
    pairs = generator.generate_contrastive_perturbations(clean_code=code, prompt=prompt, test_code=test_code)

    if not pairs:
        console.print("[yellow]No valid contrastive pairs with measurable margin could be synthesized.[/yellow]")
        return

    store = RLHFStore()
    table = Table(title="Synthesized Contrastive Dialogue Pairs (RLCD)", safe_box=True)
    table.add_column("Pair ID", style="cyan bold")
    table.add_column("Chosen Reward", justify="right")
    table.add_column("Rejected Reward", justify="right")
    table.add_column("Margin Delta", justify="right", style="green bold")
    table.add_column("Critique", style="dim")

    for p in pairs:
        # Persist to store
        store.record_pair(
            prompt=p.prompt,
            chosen=p.chosen,
            rejected=p.rejected,
            margin_score=p.margin_score,
            source="rlcd_cli",
        )
        table.add_row(
            p.pair_id,
            f"{p.chosen_reward:+.3f}",
            f"{p.rejected_reward:+.3f}",
            f"{p.margin_score:+.3f}",
            p.critique[:60] + "...",
        )

    console.print(table)
    console.print(f"[bold green]Saved {len(pairs)} verified contrastive pairs to preference store.[/bold green]")


@align_group.command("dpo-export")
@click.argument("output_path", type=click.Path())
@click.option("--min-margin", default=0.15, type=float, help="Minimum reward margin threshold.")
@click.option("--limit", default=1000, type=int, help="Maximum number of pairs to export.")
def align_dpo_export_cmd(output_path: str, min_margin: float, limit: int) -> None:
    """Exports curated preference pairs to JSONL format for Hugging Face TRL DPOTrainer."""
    from saleha.core.alignment.preference_store import DPOBatchExporter

    exporter = DPOBatchExporter()
    count = exporter.export_to_jsonl(output_path, min_margin=min_margin, limit=limit)
    console.print(f"[bold green]Successfully exported {count} DPO pairs (min margin >= {min_margin}) to:[/] {output_path}")
