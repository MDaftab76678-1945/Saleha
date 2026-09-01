"""
Saleha Interactive Developer Quickstart Wizard CLI.
Provides an interactive menu guiding developers through all engines:
- Web Studio 2.0 Glassmorphic IDE
- End-to-End Dogfooding Simulation
- Hardware & Algorithmic Micro-Benchmarks
- Monorepo Architecture Inspection
- System Specifications & Model Status
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from saleha import __version__

console = Console()


@click.command(name="start", help="Interactive developer launcher and quickstart wizard.")
@click.option("--choice", "-c", type=int, default=None, help="Directly select menu option (1-5).")
def start_cmd(choice: int | None):
    console.print(Panel(
        f"[bold cyan]🚀 SALEHA AI QUICKSTART LAUNCHER (v{__version__})[/bold cyan]\n"
        "[dim]Choose an action to launch or inspect the autonomous ecosystem:[/dim]",
        border_style="cyan"
    ))

    options = {
        1: ("Launch Web Studio 2.0 IDE", "saleha doom web --port 8000"),
        2: ("Run End-to-End Dogfooding Simulation", "saleha dogfood"),
        3: ("Run Hardware & Algorithmic Benchmarks", "saleha benchmark -n 5000"),
        4: ("Inspect Monorepo Packages & Workspaces", "saleha monorepo status"),
        5: ("View System Specifications & Capabilities", "saleha info"),
    }

    for idx, (label, cmd) in options.items():
        console.print(f"  [bold yellow][{idx}][/bold yellow] [bold white]{label}[/bold white] [dim]({cmd})[/dim]")

    if choice is None:
        try:
            choice_str = Prompt.ask("\n[bold cyan]Select an option[/bold cyan]", choices=["1", "2", "3", "4", "5", "q"], default="1")
            if choice_str == "q":
                console.print("[dim]Exiting launcher.[/dim]")
                return
            choice = int(choice_str)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting launcher.[/dim]")
            return

    if choice == 1:
        console.print("\n[bold green]Starting Web Studio 2.0 on http://127.0.0.1:8000...[/bold green]")
        from saleha.server.web_server import run_web_studio
        run_web_studio(host="127.0.0.1", port=8000, open_browser=True)
    elif choice == 2:
        from saleha.cli.demo_cli import dogfood_cmd
        ctx = click.get_current_context()
        ctx.invoke(dogfood_cmd)
    elif choice == 3:
        from saleha.cli.benchmark_cli import benchmark_cmd
        ctx = click.get_current_context()
        ctx.invoke(benchmark_cmd, iterations=5000)
    elif choice == 4:
        from saleha.cli.monorepo_cli import status_cmd
        ctx = click.get_current_context()
        ctx.invoke(status_cmd)
    elif choice == 5:
        from saleha.cli.info_cli import info_cmd
        ctx = click.get_current_context()
        ctx.invoke(info_cmd)

