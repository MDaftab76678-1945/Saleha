"""
CLI: `saleha autonomous` -- Level 5 Autonomous Engineering Kernel Dispatcher.

Executes closed-loop operations: CPG backward slicing, blast-radius analysis,
blackboard coordination, AST quality gating, and cryptographic flight recording.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import click
from rich.panel import Panel
from rich.table import Table

from saleha.cli.commands import cli, console

# Resolve script path
REPO_ROOT = Path(__file__).resolve().parents[3]
KERNEL_SCRIPT = REPO_ROOT / ".agents" / "scripts" / "autonomous_kernel.py"
FLIGHT_SCRIPT = REPO_ROOT / ".agents" / "scripts" / "flight_recorder.py"
MUTATION_SCRIPT = REPO_ROOT / ".agents" / "skills" / "mutation-engine" / "scripts" / "run_mutation_test.py"


def _load_kernel_class() -> Any:
    """Loads AutonomousKernel class dynamically from .agents/scripts."""
    spec = importlib.util.spec_from_file_location("autonomous_kernel", str(KERNEL_SCRIPT))
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load kernel script at {KERNEL_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.AutonomousKernel


def _load_mutation_runner() -> Any:
    """Loads run_mutation_audit function dynamically from .agents/skills."""
    spec = importlib.util.spec_from_file_location("mutation_runner", str(MUTATION_SCRIPT))
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load mutation script at {MUTATION_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_mutation_audit


@cli.command("autonomous")
@click.argument("target_file", default="saleha/core/math_logic.py")
@click.option("--line", "-l", type=int, default=None, help="Target line for CPG backward slicing.")
@click.option("--test-cmd", "-c", default=None, help="Optional test verification command.")
@click.option("--mutation", "-m", is_flag=True, help="Run mutation test suite verification.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON output.")
def autonomous_cmd(
    target_file: str,
    line: Optional[int],
    test_cmd: Optional[str],
    mutation: bool,
    as_json: bool,
) -> None:
    """Execute target file through the Level 5 Autonomous Kernel pipeline."""
    kernel_cls = _load_kernel_class()
    kernel = kernel_cls(repo_root=REPO_ROOT)

    if not as_json:
        console.print(
            Panel(
                f"[bold white]Target File:[/] [cyan]{target_file}[/]\n"
                f"[bold white]Pipeline:[/] [magenta]CPG Slicing -> Blast Radius -> AST Quality -> Flight Recorder[/]\n"
                f"[bold white]Target Line:[/] [yellow]{line or 'Full File'}[/]",
                title="[bold green]Saleha Autonomous Master Kernel (Level 5)[/]",
                border_style="green",
                safe_box=True,
            )
        )

    # Run Autonomous Kernel cycle
    result = kernel.execute_task_cycle(target_file, target_line=line, test_command=test_cmd)

    # Optional Mutation Testing
    mutation_result = None
    if mutation:
        runner = _load_mutation_runner()
        test_to_run = test_cmd or result.get("recommended_test_command", "python -m pytest saleha/tests/ -q")
        abs_target = (REPO_ROOT / target_file).resolve()
        mutation_result = runner(abs_target, test_to_run, max_mutants=3)
        result["mutation_audit"] = mutation_result

    if as_json:
        console.print_json(json.dumps(result))
        return

    # Visual Table Reporting
    table = Table(title="Autonomous Execution Summary", safe_box=True, show_header=True)
    table.add_column("Stage / Metric", style="cyan bold")
    table.add_column("Status / Measurement", style="green")

    table.add_row("Execution Status", str(result["status"]))
    table.add_row("Blast Radius Severity", str(result["blast_radius_severity"]))
    table.add_row("Impacted Test Suites", str(result["affected_tests_count"]))
    table.add_row("AST Quality Score", f"{result['quality_score']}/100")

    if result.get("cpg_reduction"):
        red = result["cpg_reduction"]
        table.add_row("CPG Context Slicing", f"{red['sliced_lines']} lines ({red['reduction_percent']}% reduction)")

    if mutation_result:
        score = mutation_result.get("mutation_score_percent", 0.0)
        table.add_row("Mutation Kill Score", f"{score}% ({mutation_result.get('killed_mutants', 0)} killed)")

    console.print(table)
    console.print(f"\n[bold white]Recommended Test Verification Command:[/] [yellow]{result['recommended_test_command']}[/]")
    console.print("[dim]Cryptographic event logged to .agents/scratch/flight_recorder.jsonl[/]")
