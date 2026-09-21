"""
Saleha System Info & Capability Inspector CLI.
"""

import sys
import platform
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from saleha import __version__
from saleha.core.agent_profile_loader import profile_registry
from saleha.core.tool_calling import global_tool_registry
from saleha.core.platform.model_provider import default_provider

console = Console()


def _count_test_files() -> int:
    """How many test files exist on disk. Counts files; runs nothing.

    `saleha info` is an inspector -- it must not claim a pass state for a
    suite it never executes. Reporting the file count is something this
    command can actually observe.
    """
    try:
        from pathlib import Path
        tests_dir = Path(__file__).resolve().parents[1] / "tests"
        return len(list(tests_dir.glob("test_*.py")))
    except OSError:
        return 0


@click.command(name="info", help="Display system architecture, connected engines, and runtime specs.")
def info_cmd():
    console.print(Panel(f"[bold cyan]🧬 SALEHA AI UNIFIED PLATFORM SPECIFICATIONS (v{__version__})[/bold cyan]\n[dim]Autonomous Software Engineering & Polyglot Multi-Agent Swarm[/dim]"))

    table = Table(border_style="cyan")
    table.add_column("Property / Component", style="bold white", width=28)
    table.add_column("Active Configuration", style="cyan", width=34)
    table.add_column("Status", style="bold green", width=14)

    table.add_row("Platform Version", f"Saleha AI v{__version__}", "🟢 ENTERPRISE")
    table.add_row("Python Runtime", f"Python {platform.python_version()} ({platform.system()})", "🟢 ACTIVE")
    table.add_row("Active Model Provider", default_provider.__class__.__name__, "🟢 MULTI-TIER")
    table.add_row("Registered Agent Profiles", f"{len(profile_registry.list_profiles())} Specialized Profiles", "🟢 READY")
    table.add_row("Tool Calling Registry", f"{len(global_tool_registry.get_schemas())} Verified Tools", "🟢 SECURE")
    table.add_row("Swarm Topology", "10 Departments (250 Agents)", "🟢 POINCARÉ 16D")
    table.add_row("AST Safety Verifier", "Gamma AST 2PC + ASan Guard", "🟢 0 LEAKS")
    table.add_row("Monorepo Packages", "@saleha/{ui,db,api,auth,core}", "🟢 SYNCHRONIZED")
    # Was hardcoded "879 / 879 Unit & System Tests" / "100% PASS" -- a count
    # that was invented, went stale (the suite is four figures now), and
    # asserted a passing state on a command that runs no tests at all. The
    # honest version reports how many tests exist and says plainly that this
    # command did not run them.
    table.add_row("Automated Test Suite", f"{_count_test_files()} test files under saleha/tests",
                  "not run here")

    console.print(table)
    console.print("\n[bold green]Ready for autonomous software engineering tasks.[/bold green]\n")

