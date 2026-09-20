"""Auto-extracted from the former monolithic saleha/cli/commands.py.

Imports `cli` to register commands against the same Click group, and `_cmds`
(the package module itself) so any reference to a lazily-imported name (see
_LAZY_IMPORT_MAP in __init__.py) or a shared helper resolves through the
original module -- this keeps mock.patch("saleha.cli.commands.X") working
for tests that patch those names, and preserves the PEP 562 lazy-loading
behavior for whatever this file's commands use.
"""
import click
from saleha.cli.commands import cli, console
from saleha.cli import commands as _cmds

from typing import Any, Dict, List, Optional
import click
from rich.table import Table
from saleha.cli.commands import cli, console


@cli.group()
def self_improve() -> None:
    """Autonomous self-improvement: finds an untested core module, writes and
    verifies a real test for it, commits to auto/self-improve locally. Never
    pushes to a remote -- that stays a human decision."""


@self_improve.command(name="run")
@click.option("--cycles", "-c", default=1, type=int, help="Number of self-improvement cycles to run.")
@click.option("--max-repairs", default=2, type=int, help="Max test repair attempts per cycle.")
def self_improve_run(cycles: int = 1, max_repairs: int = 2) -> None:
    """Runs autonomous self-improvement test generation cycles."""
    if cycles > 1:
        from saleha.core.self_improve import run_self_improvement_batch, SelfImproveResult

        def on_cycle(idx: int, total: int, res: SelfImproveResult) -> None:
            color = "green" if res.status == "committed" else "yellow"
            console.print(f"[{idx}/{total}] [bold {color}]{res.status}[/] — {res.module or '(none)'}")
            if res.status == "committed":
                sha = res.commit_sha[:10] if res.commit_sha else "unknown"
                console.print(f"       branch: {res.branch}  commit: {sha}")
            elif res.detail:
                console.print(f"       {res.detail[:200]}")

        console.print(f"[bold cyan]Starting self-improvement batch: {cycles} cycle(s)...[/bold cyan]")
        results = run_self_improvement_batch(cycles=cycles, max_repairs=max_repairs, callback=on_cycle)
        committed = sum(1 for r in results if r.status == "committed")
        console.print(f"\n[bold]Batch completed:[/] {committed}/{len(results)} module tests committed.")
    else:
        from saleha.core.self_improve import run_self_improvement_cycle
        result = run_self_improvement_cycle(max_repairs=max_repairs)
        color = "green" if result.status == "committed" else "yellow"
        console.print(f"[bold {color}]{result.status}[/] — {result.module or '(none)'}")
        if result.status == "committed":
            sha = result.commit_sha[:10] if result.commit_sha else "unknown"
            console.print(f"  branch: {result.branch}  commit: {sha}")
        else:
            console.print(f"  {result.detail[:300]}")


@self_improve.command(name="status")
def self_improve_status() -> None:
    """Displays current self-improvement test coverage and audit stats."""
    from saleha.core.self_improve import get_self_improvement_status

    status = get_self_improvement_status()

    table = Table(title="Saleha Self-Improvement Engine Status", safe_box=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Total Core Modules", str(status.get("total_core_modules", 0)))
    table.add_row("Tested Modules (Total)", str(status.get("tested_modules_count", 0)))
    table.add_row("  - Tested Locally", str(status.get("tested_local_count", 0)))
    table.add_row("  - Tested on auto/self-improve", str(status.get("tested_auto_branch_count", 0)))
    table.add_row("Untested Core Modules", str(status.get("untested_modules_count", 0)))
    cov = status.get("test_coverage_pct", 0.0)
    cov_color = "green" if cov >= 90 else ("yellow" if cov >= 70 else "red")
    table.add_row("Test Coverage", f"[{cov_color}]{cov}%[/]")
    table.add_row("Recent Logged Cycles", str(status.get("total_logged_cycles", 0)))
    table.add_row("Recent Committed Cycles", str(status.get("recent_committed_cycles", 0)))
    rate = status.get("recent_success_rate_pct", 0.0)
    table.add_row("Recent Pass Rate", f"{rate}%")

    console.print(table)

    untested: List[str] = status.get("untested_modules", [])
    if untested:
        preview = ", ".join(untested[:8])
        if len(untested) > 8:
            preview += f", ... (+{len(untested) - 8} more)"
        console.print(f"\n[bold yellow]Untested candidates:[/] {preview}")


@self_improve.command(name="log")
@click.option("--limit", default=20, type=int, help="Number of recent log entries to show.")
def self_improve_log(limit: int = 20) -> None:
    """Displays recent audit log entries from self-improvement engine."""
    from saleha.core.self_improve import read_log
    entries = read_log(limit)
    if not entries:
        console.print("[dim]No self-improvement logs recorded yet.[/dim]")
        return
    for entry in entries:
        ts = entry.get("timestamp", "")
        st = entry.get("status", "")
        mod = entry.get("module", "")
        color = "green" if st == "committed" else "yellow"
        console.print(f"  [{ts}] [{color}]{st:18}[/] {mod}")

