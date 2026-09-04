"""
Saleha Soul CLI - Cognitive Persona & SoulSpec Management
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from saleha.core.soul_engine import soul_engine

console = Console(safe_box=True)


@click.group("soul")
def soul_group():
    """Manage SoulSpec cognitive personas and behavioral archetypes."""
    pass


@soul_group.command("list")
def list_souls_cmd():
    """List all available SoulSpec personas and display the active soul."""
    souls = soul_engine.list_souls()
    active_name = soul_engine.get_active_soul_name()

    table = Table(
        title="[bold cyan]🌌 Saleha Cognitive Personas (SoulSpec v1.0)[/bold cyan]",
        border_style="cyan",
        header_style="bold magenta",
        show_lines=True
    )
    table.add_column("Status", justify="center", style="bold", width=10)
    table.add_column("Identifier", style="bold white", width=14)
    table.add_column("Display Name", style="cyan", width=26)
    table.add_column("Archetype", style="green", width=30)
    table.add_column("Description", style="dim white")

    for s in souls:
        is_active = s.name == active_name
        status = "[bold green]● ACTIVE[/]" if is_active else "[dim]○ standby[/]"
        name_styled = f"[bold yellow]{s.name}[/]" if is_active else s.name
        table.add_row(
            status,
            name_styled,
            s.display_name,
            s.archetype,
            s.description
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Active Soul:[/] [bold green]{active_name}[/] | Switch using: [cyan]saleha soul use <name>[/]\n")


@soul_group.command("use")
@click.argument("name")
def use_soul_cmd(name: str):
    """Switch the framework's active cognitive persona."""
    try:
        active = soul_engine.set_active_soul(name)
        console.print()
        console.print(Panel(
            f"[bold green]✓ Activated Persona:[/] [bold cyan]{active.display_name}[/] ([italic yellow]{active.name}[/])\n\n"
            f"[bold white]Archetype:[/] {active.archetype}\n"
            f"[bold white]Description:[/] {active.description}\n"
            f"[bold white]Tags:[/] {', '.join(active.tags)}\n\n"
            f"[dim]All autonomous agents and reasoning loops will now operate under this soul.[/]",
            title="[bold green]🌌 Soul Transition Complete[/]",
            border_style="green"
        ))
        console.print()
    except KeyError as e:
        console.print()
        console.print(Panel(
            f"[bold red]Error:[/] {e}\n\n"
            f"[dim]Run [bold cyan]saleha soul list[/] to see all available archetypes.[/]",
            title="[bold red]Activation Failed[/]",
            border_style="red"
        ))
        console.print()


@soul_group.command("show")
@click.argument("name", required=False)
def show_soul_cmd(name: str | None = None):
    """Inspect the full SoulSpec persona, directives, and identity."""
    target_name = name or soul_engine.get_active_soul_name()
    soul = soul_engine.get_soul(target_name)

    if not soul:
        console.print(f"[bold red]Error:[/] Soul '{target_name}' not found.")
        return

    console.print()
    header = (
        f"# {soul.display_name} (`{soul.name}`)\n"
        f"**Archetype:** {soul.archetype} | **Version:** {soul.version}\n\n"
        f"{soul.description}\n\n"
        f"---\n\n"
    )
    full_doc = header + soul.soul_md

    if soul.identity_md:
        full_doc += "\n\n---\n\n" + soul.identity_md

    if soul.style_md:
        full_doc += "\n\n---\n\n" + soul.style_md

    console.print(Markdown(full_doc))
    console.print()


@soul_group.command("validate")
def validate_souls_cmd():
    """Validate all souls in the library against SoulSpec v1.0 standard."""
    report = soul_engine.validate_all()
    console.print()
    if report["invalid_souls"] == 0:
        console.print(Panel(
            f"[bold green]✓ All {report['total_souls']} SoulSpec personas are 100% valid and verified![/bold green]\n"
            f"[dim]Every package contains valid JSON manifests, non-empty SOUL.md, and conforms to markdownlint.[/dim]",
            title="[bold green]SoulSpec Integrity Verification[/]",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]Found {report['invalid_souls']} invalid souls![/bold red]\n"
            f"Details: {report['errors']}",
            title="[bold red]Validation Errors[/]",
            border_style="red"
        ))
    console.print()
