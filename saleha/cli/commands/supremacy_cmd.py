"""
CLI: `saleha supremacy` -- Test-Time Compute (TTC) & Reflexion Tournament Engine.

Executes Step 4 of the Master Vision (Small Beating Large):
Enabling a 4GB/3B local model to outperform 200B parameter frontier models.

Empowers local 3B/8B models to beat large single-shot models via multi-trajectory
exploration, dual AST verification, sandbox testing, and traceback reflexion.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from saleha.cli.commands import cli, console


@cli.command("supremacy")
@click.argument("problem", default="Implement a function find_first_unique_char(s: str) -> int returning index of first non-repeating char or -1")
@click.option("--tests", "-t", default="", help="Python test assertions string or path to test file")
@click.option("--model", "-m", default="qwen2.5-coder:3b", help="Local model to amplify (default: qwen2.5-coder:3b)")
@click.option("--trajectories", "-k", default=4, help="Number of parallel candidate trajectories (default: 4)")
@click.option("--refinements", "-r", default=2, help="Maximum reflexion self-repair rounds (default: 2)")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON tournament payload")
def supremacy_cmd(
    problem: str,
    tests: str,
    model: str,
    trajectories: int,
    refinements: int,
    as_json: bool,
) -> None:
    """Amplify local small models to beat large single-shot models via Test-Time Compute."""
    from saleha.core.local_supremacy import LocalSupremacyEngine, CandidateEvaluation

    # Resolve test suite if provided as a file path
    test_suite = tests
    if tests and os.path.isfile(tests):
        try:
            test_suite = Path(tests).read_text(encoding="utf-8")
        except Exception:
            test_suite = tests
    elif not test_suite and "find_first_unique_char" in problem:
        # Default built-in test suite for default problem demo
        test_suite = (
            "assert find_first_unique_char('leetcode') == 0\n"
            "assert find_first_unique_char('loveleetcode') == 2\n"
            "assert find_first_unique_char('aabb') == -1\n"
            "assert find_first_unique_char('') == -1\n"
        )

    engine = LocalSupremacyEngine(
        model=model,
        num_trajectories=trajectories,
        max_refinements=refinements,
    )

    if not as_json:
        console.print(
            Panel(
                f"[bold white]Target Mission:[/] [cyan]{problem}[/]\n"
                f"[bold white]Local Model:[/] [yellow]{model}[/] | [bold white]Search Budget:[/] [green]{trajectories} Trajectories[/] | [bold white]Reflexion Depth:[/] [magenta]{refinements} Attempts[/]\n"
                f"[bold white]Test Suite:[/] [white]{len(test_suite.splitlines())} assertion lines[/]",
                title="[bold green]Local Supremacy Engine (Small Beating Large)[/]",
                border_style="green",
                safe_box=True,
            )
        )

    traj_table = Table(title="Candidate Trajectory Tournament", safe_box=True, show_header=True)
    traj_table.add_column("ID", style="cyan bold")
    traj_table.add_column("Strategy", style="white")
    traj_table.add_column("Temp", style="yellow")
    traj_table.add_column("Syntax", style="green")
    traj_table.add_column("Security", style="blue")
    traj_table.add_column("Sandbox Tests", style="magenta bold")
    traj_table.add_column("Latency", style="dim")

    def on_event(ev: dict) -> None:
        if not as_json and ev.get("type") == "candidate_evaluated":
            cand: CandidateEvaluation = ev["candidate"]
            syntax_str = "[green]VALID[/]" if cand.syntax_valid else "[red]SYNTAX_ERR[/]"
            sec_str = "[green]CLEAN[/]" if cand.security_clean else "[yellow]CWE_RISK[/]"
            test_str = "[bold green]PASSED[/]" if cand.tests_passed else f"[bold red]EXIT_{cand.exit_code}[/]"
            traj_table.add_row(
                cand.candidate_id,
                cand.strategy_name,
                f"{cand.temperature:.1f}",
                syntax_str,
                sec_str,
                test_str,
                f"{cand.execution_time_ms}ms",
            )

    if as_json:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            result = engine.solve(problem=problem, test_suite=test_suite, callback=on_event)
    else:
        result = engine.solve(problem=problem, test_suite=test_suite, callback=on_event)

    if as_json:
        payload = {
            "problem": result.problem,
            "model": model,
            "passed": result.passed,
            "winner_id": result.winner_id,
            "winner_code": result.winner_code,
            "single_shot_passed": result.single_shot_passed,
            "amplification_factor": result.amplification_factor if result.amplification_factor != float("inf") else "infinite",
            "total_candidates": result.total_candidates,
            "total_repairs": result.total_repairs,
            "total_duration_ms": result.total_duration_ms,
            "candidates": [
                {
                    "id": c.candidate_id,
                    "strategy": c.strategy_name,
                    "temperature": c.temperature,
                    "syntax_valid": c.syntax_valid,
                    "security_clean": c.security_clean,
                    "tests_passed": c.tests_passed,
                    "exit_code": c.exit_code,
                    "latency_ms": c.execution_time_ms,
                    "score": c.score,
                    "error": c.error_summary,
                }
                for c in result.candidates
            ],
            "repairs": [
                {
                    "attempt": r.attempt_number,
                    "parent_id": r.parent_candidate_id,
                    "error_type": r.error_type,
                    "tests_passed": r.tests_passed,
                    "exit_code": r.exit_code,
                    "latency_ms": r.execution_time_ms,
                }
                for r in result.repairs
            ],
            "summary": result.summary,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    console.print(traj_table)

    if result.repairs:
        rep_table = Table(title="Reflexion Self-Correction Traceback Log", safe_box=True, show_header=True)
        rep_table.add_column("Attempt", style="cyan bold")
        rep_table.add_column("Parent ID", style="yellow")
        rep_table.add_column("Error Diagnosis", style="white")
        rep_table.add_column("Re-Test Status", style="green bold")
        rep_table.add_column("Latency", style="dim")
        for r in result.repairs:
            status_style = "[bold green]PASSED[/]" if r.tests_passed else f"[bold red]EXIT_{r.exit_code}[/]"
            rep_table.add_row(
                f"Round {r.attempt_number}",
                r.parent_candidate_id,
                r.error_summary[:60],
                status_style,
                f"{r.execution_time_ms}ms",
            )
        console.print(rep_table)

    status_color = "bold green" if result.passed else "bold red"
    status_text = "VERIFIED TOURNAMENT WINNER" if result.passed else "EXECUTION FAILED"
    amp_text = "+100% (recovered from 0% single-shot failure)" if result.amplification_factor == float("inf") else f"{result.amplification_factor:.1f}x"

    console.print(
        Panel(
            f"[{status_color}]Result: {status_text}[/]\n\n"
            f"[bold cyan]Winning Trajectory:[/] [yellow]{result.winner_id}[/]\n"
            f"[bold cyan]Single-Shot Baseline:[/] {'[green]PASSED[/]' if result.single_shot_passed else '[red]FAILED[/]'}\n"
            f"[bold cyan]TTC Amplification:[/] [green bold]{amp_text}[/]\n"
            f"[bold cyan]Total Search Time:[/] {result.total_duration_ms}ms\n\n"
            f"[dim]Synthesized Python Code:[/]\n"
            f"```python\n{result.winner_code[:400] + ('...' if len(result.winner_code) > 400 else '')}\n```",
            title="[bold green]Supremacy Synthesis Deliverable[/]",
            border_style="green" if result.passed else "red",
            safe_box=True,
        )
    )
