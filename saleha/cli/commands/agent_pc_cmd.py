"""CLI: `saleha pc` -- Agent Personal Computer, Sandbox & Blackbox Manager.

Inspects agent virtual workstations, monitors sandbox security, and
replays cryptographic flight recorder traces.
"""

from __future__ import annotations

import click
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from saleha.cli.commands import cli, console


@cli.group("pc")
def pc_group() -> None:
    """Agent Personal Computer (AgentPC): Workspaces, Sandboxes & Flight Recorders."""


@pc_group.command("status")
def pc_status_cmd() -> None:
    """Lists operational status of all Agent Personal Computers."""
    from saleha.core.sandbox.agent_pc import list_active_agent_pcs

    pcs = list_active_agent_pcs()
    if not pcs:
        console.print("[dim]No active agent personal computers found.[/dim]")
        return

    table = Table(title="Saleha Agent Personal Computers", safe_box=True)
    table.add_column("Agent Role", style="cyan bold")
    table.add_column("Files", justify="right")
    table.add_column("Disk Usage", justify="right")
    table.add_column("Checkpoints", justify="right")
    table.add_column("Blackbox Events", justify="right")
    table.add_column("Chain Integrity", style="bold")

    for pc in pcs:
        bytes_str = f"{pc['total_bytes'] / 1024:.1f} KB" if pc['total_bytes'] > 1024 else f"{pc['total_bytes']} B"
        status_color = "green" if pc["blackbox_intact"] else "red"
        status_text = f"[{status_color}]{'INTACT' if pc['blackbox_intact'] else 'COMPROMISED'}[/]"

        table.add_row(
            pc["agent_role"],
            str(pc["files_count"]),
            bytes_str,
            str(pc["checkpoints_count"]),
            str(pc["blackbox_events_count"]),
            status_text,
        )

    console.print(table)


@pc_group.command("inspect")
@click.argument("agent_role")
def pc_inspect_cmd(agent_role: str) -> None:
    """Inspects an agent's personal computer, workspace files, and flight log."""
    from saleha.core.sandbox.agent_pc import get_agent_pc

    pc = get_agent_pc(agent_role)
    summary = pc.get_pc_summary()

    console.print(Panel(
        f"[bold cyan]Role:[/] {summary['agent_role']}\n"
        f"[bold cyan]Workspace:[/] {summary['workspace_dir']}\n"
        f"[bold cyan]Files:[/] {summary['files_count']} ({summary['total_bytes']} bytes)\n"
        f"[bold cyan]Checkpoints:[/] {summary['checkpoints_count']}\n"
        f"[bold cyan]Blackbox Events:[/] {summary['blackbox_events_count']} "
        f"({'[green]INTACT[/]' if summary['blackbox_intact'] else '[red]COMPROMISED[/]'})",
        title=f"Agent PC: {agent_role.upper()}",
        border_style="cyan",
    ))

    # Workspace Files
    files = summary.get("files", [])
    if files:
        tree = Tree(f"[bold green]Workspace Files ({len(files)})[/]")
        for f in files:
            tree.add(f)
        console.print(tree)
    else:
        console.print("[dim]Workspace is clean (no user files).[/dim]")

    # Checkpoints
    chks = pc.workspace.list_checkpoints()
    if chks:
        chk_table = Table(title="Time-Travel Checkpoints", safe_box=True)
        chk_table.add_column("Checkpoint ID", style="yellow")
        chk_table.add_column("Tag", style="bold")
        chk_table.add_column("Files Included", justify="right")
        for c in chks:
            chk_table.add_row(c.get("checkpoint_id", ""), c.get("tag", ""), str(len(c.get("files", []))))
        console.print(chk_table)

    # Recent Blackbox Events
    events = summary.get("recent_events", [])
    if events:
        ev_table = Table(title="Recent Blackbox Flight Events", safe_box=True)
        ev_table.add_column("Timestamp", style="dim")
        ev_table.add_column("Type", style="bold")
        ev_table.add_column("Stage")
        ev_table.add_column("Status")

        for ev in events:
            color = "green" if ev.get("status") in ("SUCCESS", "PASS", "WRITTEN", "INITIALIZED") else "yellow"
            ev_table.add_row(
                str(ev.get("timestamp", ""))[:19],
                ev.get("event_type", ""),
                ev.get("stage", ""),
                f"[{color}]{ev.get('status', '')}[/]",
            )
        console.print(ev_table)


@pc_group.command("replay")
@click.argument("agent_role")
@click.option("--limit", "-n", type=int, default=20, help="Number of flight events to replay.")
def pc_replay_cmd(agent_role: str, limit: int) -> None:
    """Replays deterministic blackbox execution trace for an agent."""
    from saleha.core.sandbox.agent_pc import get_agent_pc

    pc = get_agent_pc(agent_role)
    trace = pc.blackbox.replay(limit=limit)

    if not trace:
        console.print(f"[dim]No blackbox events recorded for agent '{agent_role}'.[/dim]")
        return

    console.print(f"\n[bold cyan]Deterministic Flight Replay: {agent_role.upper()}[/] ({len(trace)} events)\n")
    for step in trace:
        color = "green" if step["status"] in ("SUCCESS", "PASS", "WRITTEN", "INITIALIZED") else "yellow"
        console.print(
            f"[{step['time']}] [{color}]{step['status']:12}[/] [bold]{step['type']:18}[/] "
            f"([cyan]{step['stage']}[/]) — {step['summary'][:80]}"
        )


@pc_group.command("clean")
@click.argument("agent_role")
@click.option("--all-data", is_flag=True, help="Also remove checkpoints and scratchpad.")
def pc_clean_cmd(agent_role: str, all_data: bool) -> None:
    """Cleans an agent's personal computer workspace."""
    from saleha.core.sandbox.agent_pc import get_agent_pc

    pc = get_agent_pc(agent_role)
    count = pc.workspace.clear_workspace(preserve_metadata=not all_data)
    console.print(f"[green]Cleaned agent PC '{agent_role}': deleted {count} workspace file(s).[/green]")
