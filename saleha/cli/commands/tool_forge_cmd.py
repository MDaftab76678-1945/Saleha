"""CLI: `saleha tools` & `saleha forge-tool` -- autonomous tool creation and registry inspection.

Wires the existing `saleha.core.tool_forge.ToolForge` engine (model
generation, QualityGuard + AST structural checks, isolated pytest run,
git commit) and `saleha.tools.base.tool_registry` to the CLI.
"""
from typing import Any, Dict, Tuple
import json
import click
from rich.panel import Panel
from rich.table import Table

from saleha.cli.commands import cli, console


def _execute_forge(name: str, description: str, params: Tuple[str, ...], domain: str, no_commit: bool) -> None:
    from saleha.core.tool_forge import ToolForge, ToolSpecification

    parameters: Dict[str, Any] = {"type": "object", "properties": {}}
    properties: Dict[str, Any] = {}
    for p in params:
        if ":" not in p:
            console.print(f"[bold red]Invalid --param '{p}', expected name:type[/bold red]")
            raise SystemExit(1)
        pname, ptype = p.split(":", 1)
        properties[pname] = {"type": ptype, "description": f"Parameter {pname}"}

    if properties:
        parameters["properties"] = properties

    spec = ToolSpecification(
        name=name,
        class_name="".join(part.capitalize() for part in name.split("_")) + "Tool",
        description=description,
        parameters=parameters,
        domain=domain,
    )

    forge = ToolForge()
    result = forge.forge_tool(spec, auto_commit=not no_commit)

    if result.status == "created":
        console.print(f"[bold green]Forged tool '{name}'[/bold green] -> {result.tool_path}")
        console.print(f"  test: {result.test_path}")
        if result.commit_sha:
            console.print(f"  committed: {result.commit_sha[:10]}")
        console.print(f"  {result.detail}")
    elif result.status == "already_exists":
        console.print(f"[yellow]{result.detail}[/yellow]")
    else:
        console.print(f"[bold red]Forge failed ({result.status}):[/bold red] {result.detail}")
        raise SystemExit(1)


@cli.command(name="forge-tool")
@click.argument("name")
@click.argument("description")
@click.option(
    "--param",
    "params",
    multiple=True,
    help="Tool parameter as name:type, repeatable (e.g. --param path:str --param limit:int)",
)
@click.option("--domain", default="general", help="Tool domain/category")
@click.option(
    "--no-commit",
    is_flag=True,
    help="Write and validate the tool but do not git-commit it",
)
def forge_tool_cmd(
    name: str, description: str, params: Tuple[str, ...], domain: str, no_commit: bool
) -> None:
    """Autonomously synthesize a new tool."""
    _execute_forge(name, description, params, domain, no_commit)


@cli.group(name="tools", invoke_without_command=True)
@click.pass_context
@click.option("--json", "as_json", is_flag=True, help="Print a machine-readable JSON response")
def tools_group(ctx: click.Context, as_json: bool) -> None:
    """Inspect and manage Saleha tool catalog and dynamic tools."""
    if ctx.invoked_subcommand is None:
        from saleha.cli import commands as _cmds

        registered = _cmds.global_tool_registry.list_tools()
        if as_json:
            click.echo(json.dumps({"tools": _cmds.global_tool_registry.get_schemas()}, ensure_ascii=True))
            return
        table = Table(title="Registered Dynamic Agent Tools", show_header=True, header_style="bold magenta", safe_box=True)
        table.add_column("Tool Name", style="cyan")
        table.add_column("Parameters", style="green")
        table.add_column("Description", style="yellow")
        for t in registered:
            params_str = ", ".join([f"{p.name}: {p.type}" for p in t.parameters]) or "None"
            table.add_row(t.name, params_str, t.description)
        console.print(table)


@tools_group.command(name="list")
def tools_list() -> None:
    """Lists all currently available tools in the tool registry."""
    from saleha.tools.base import tool_registry

    tool_registry.auto_discover()
    registered = tool_registry.list_tools()

    table = Table(title="Registered Saleha Tools", safe_box=True)
    table.add_column("Tool Name", style="cyan bold")
    table.add_column("Class", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Parameters", style="green")

    for t in sorted(registered, key=lambda x: x.name):
        props = t.parameters.get("properties", {}) if isinstance(t.parameters, dict) else {}
        param_names = ", ".join(props.keys()) or "(none)"
        desc = (t.description or "").strip().splitlines()[0] if t.description else "(no description)"
        table.add_row(t.name, t.__class__.__name__, desc[:60], param_names)

    console.print(table)
    console.print(f"\n[dim]Total registered tools: {len(registered)}[/dim]")


@tools_group.command(name="info")
@click.argument("name")
def tools_info(name: str) -> None:
    """Displays detailed information and JSON Schema for a registered tool."""
    from saleha.tools.base import tool_registry

    tool_registry.auto_discover()
    tool = tool_registry.get(name)

    if not tool:
        console.print(f"[bold red]Tool '{name}' not found in registry.[/bold red]")
        raise SystemExit(1)

    console.print(Panel(
        f"[bold cyan]{tool.name}[/] ({tool.__class__.__name__})\n\n"
        f"[bold]Description:[/]\n{tool.description or '(none)'}\n\n"
        f"[bold]Schema Definition:[/]\n{json.dumps(tool.parameters, indent=2)}",
        title=f"Tool: {tool.name}",
        safe_box=True,
    ))


@tools_group.command(name="forge")
@click.argument("name")
@click.argument("description")
@click.option(
    "--param",
    "params",
    multiple=True,
    help="Tool parameter as name:type, repeatable (e.g. --param path:str --param limit:int)",
)
@click.option("--domain", default="general", help="Tool domain/category")
@click.option(
    "--no-commit",
    is_flag=True,
    help="Write and validate the tool but do not git-commit it",
)
def tools_forge(
    name: str, description: str, params: Tuple[str, ...], domain: str, no_commit: bool
) -> None:
    """Autonomously synthesize a new tool into saleha/tools/."""
    _execute_forge(name, description, params, domain, no_commit)

