"""CLI: `saleha new` -- scaffold a runnable starter service from a template.

Separate from misc_tools.py so this command's file is self-contained. It
imports `cli` to register against the shared Click group.
"""

import click

from saleha.cli.commands import cli, console


@cli.command(name="new")
@click.argument("stack")
@click.argument("name")
@click.option("--into", default=".", help="Parent directory to create the project in")
@click.option("--force", is_flag=True, help="Overwrite the target directory if it exists")
def new_cmd(stack: str, name: str, into: str, force: bool) -> None:
    """
    Scaffold a runnable starter service from a bundled template.

    STACK is one of: fastapi, express, go. This copies the template
    verbatim (no model call, byte-identical for the same inputs) with the
    project name substituted, then runs the stack's build/test to confirm
    it works. A verification step whose toolchain is missing is reported as
    skipped, never as a pass.

    Example: saleha new fastapi orders-api
    """
    from saleha.core.project_scaffolder import project_scaffolder, TEMPLATES

    if stack.lower() not in TEMPLATES:
        console.print(
            f"[bold red]Unknown stack '{stack}'.[/bold red] "
            f"Available: {', '.join(sorted(TEMPLATES))}"
        )
        raise SystemExit(1)

    res = project_scaffolder.scaffold(stack, name, dest_parent=into, force=force)
    if res.error:
        console.print(f"[bold red]{res.error}[/bold red]")
        raise SystemExit(1)

    console.print(
        f"[bold green]Scaffolded {res.stack} project[/bold green] -> "
        f"[cyan]{res.project_dir}[/cyan] ({len(res.files_written)} files)"
    )
    if not res.verify_ran:
        console.print(f"  [yellow]Verification skipped:[/yellow] {res.verify_detail}")
    elif res.verify_ok:
        console.print("  [green]Verification passed[/green] (the scaffold builds/tests clean)")
    else:
        console.print("  [bold red]Verification FAILED[/bold red]")
        console.print(f"  [dim]{res.verify_detail}[/dim]")
        raise SystemExit(1)
