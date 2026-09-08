"""CLI: `saleha forge-tool` -- autonomously synthesize a new tool.

Wires the existing `saleha.core.tool_forge.ToolForge` engine (model
generation, QualityGuard + AST structural checks, isolated pytest run,
git commit) to the CLI. The engine already existed and was fully real;
it had no command pointing at it.
"""

import click

from saleha.cli.commands import cli, console


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
    name: str, description: str, params: tuple, domain: str, no_commit: bool
) -> None:
    """
    Autonomously synthesize a new tool: model generates the implementation
    and a pytest suite, both are validated (static inspection, structural
    checks, an isolated real pytest run) before anything touches the repo.

    NAME is the tool's snake_case identifier (e.g. word_counter).
    DESCRIPTION tells the model what the tool should do.

    Example:
      saleha forge-tool word_counter "Counts words in a text file" \\
          --param path:str
    """
    from saleha.core.tool_forge import ToolForge, ToolSpecification

    parameters = {}
    for p in params:
        if ":" not in p:
            console.print(f"[bold red]Invalid --param '{p}', expected name:type[/bold red]")
            raise SystemExit(1)
        pname, ptype = p.split(":", 1)
        parameters[pname] = ptype

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
