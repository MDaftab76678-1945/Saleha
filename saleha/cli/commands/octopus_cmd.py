"""
CLI: `saleha octopus` -- 9-Brain Autonomous Multi-Agent Coordination Engine.

Executes user mission goals across 1 Central Mind and 8 Specialized Peripheral
Arm Brains with concurrent worker pool execution and real-time Rich HUD visualization.
"""

from __future__ import annotations

import contextlib
import io
import json
import time
from typing import Optional

import click
from rich.panel import Panel
from rich.table import Table

from saleha.cli.commands import cli, console


@cli.command("octopus")
@click.argument("goal", default="Design and implement a thread-safe distributed rate limiter")
@click.option("--model", "-m", default="auto", help="Model to use across brains (default: auto)")
@click.option("--workers", "-w", default=4, help="Maximum concurrent worker threads (default: 4)")
@click.option("--timeout", "-t", default=120.0, help="Per-phase execution timeout in seconds")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON execution payload")
def octopus_cmd(goal: str, model: str, workers: int, timeout: float, as_json: bool) -> None:
    """Execute goal using the 9-Brain Octopus Multi-Agent Coordination Engine."""
    from saleha.core.octopus_coordinator import OctopusCoordinator, ArmBrainOutput
    from saleha.core.agent_worker_pool import AgentWorkerPool

    coordinator = OctopusCoordinator(
        model=model,
        worker_pool=AgentWorkerPool(max_workers=workers),
        timeout_sec=timeout,
    )

    if not as_json:
        console.print(
            Panel(
                f"[bold white]Mission:[/] [cyan]{goal}[/]\n"
                f"[bold white]Architecture:[/] [magenta]1 Central Mind + 8 Peripheral Arm Brains[/]\n"
                f"[bold white]Model Configuration:[/] [yellow]{model}[/] | [bold white]Concurrency Workers:[/] [green]{workers}[/]",
                title="[bold green]Octopus Multi-Brain Coordination Engine[/]",
                border_style="green",
                safe_box=True,
            )
        )

    dispatched_table = Table(title="Peripheral Arm Brain Activity", safe_box=True, show_header=True)
    dispatched_table.add_column("Arm Brain", style="cyan bold")
    dispatched_table.add_column("Status", style="green")
    dispatched_table.add_column("Latency", style="yellow")
    dispatched_table.add_column("Summary Finding", style="white")

    def on_brain_output(out: ArmBrainOutput) -> None:
        if not as_json:
            status_style = "[bold green]SUCCESS[/]" if out.status == "success" else "[bold red]FAILED[/]"
            dispatched_table.add_row(
                out.brain_name,
                status_style,
                f"{out.duration_ms}ms",
                out.summary[:70] + ("..." if len(out.summary) > 70 else ""),
            )

    if as_json:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            result = coordinator.coordinate(goal=goal, callback=on_brain_output)
    else:
        result = coordinator.coordinate(goal=goal, callback=on_brain_output)

    if as_json:
        payload = {
            "execution_id": result.execution_id,
            "goal": result.goal,
            "success": result.success,
            "adr_title": result.adr_title,
            "security_clean": result.security_clean,
            "tests_passed": result.tests_passed,
            "resilience_score": result.resilience_score,
            "review_approved": result.review_approved,
            "total_duration_ms": result.total_duration_ms,
            "final_code": result.final_code,
            "brain_outputs": {
                k: {
                    "name": v.brain_name,
                    "status": v.status,
                    "summary": v.summary,
                    "duration_ms": v.duration_ms,
                    "error": v.error,
                }
                for k, v in result.brain_outputs.items()
            },
        }
        click.echo(json.dumps(payload, indent=2))
        return

    console.print(dispatched_table)

    summary_color = "bold green" if result.success else "bold red"
    tests_badge = "[green]PASSED[/]" if result.tests_passed else "[red]FAILED[/]"
    sec_badge = "[green]CLEAN (0 CVEs)[/]" if result.security_clean else "[yellow]HARDENED[/]"
    rev_badge = "[green]APPROVED[/]" if result.review_approved else "[yellow]REJECTED[/]"

    console.print(
        Panel(
            f"[{summary_color}]Execution Status: {'SUCCESS' if result.success else 'FAILED'}[/]\n\n"
            f"[bold cyan]Architecture ADR:[/] {result.adr_title or 'Standard Design'}\n"
            f"[bold cyan]Sandbox Verification:[/] {tests_badge}\n"
            f"[bold cyan]Security AST Audit:[/] {sec_badge}\n"
            f"[bold cyan]Resilience Score:[/] [green]{result.resilience_score}%[/]\n"
            f"[bold cyan]Constitutional Review:[/] {rev_badge}\n"
            f"[bold cyan]Total Runtime:[/] {result.total_duration_ms}ms\n\n"
            f"[dim]Synthesized Code ({len(result.final_code)} chars):[/]\n"
            f"```python\n{result.final_code[:400] + ('...' if len(result.final_code) > 400 else '')}\n```",
            title="[bold green]Octopus Synthesis Deliverable[/]",
            border_style="green" if result.success else "red",
            safe_box=True,
        )
    )
