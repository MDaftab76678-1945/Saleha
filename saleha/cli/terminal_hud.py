"""
Saleha CLI: Live Interactive Terminal Heads-Up Display (HUD)

Renders a 4-quadrant real-time TUI dashboard showing Ollama model telemetry,
system resource load, codebase AST graph status, long-term memory metrics, and developer hotkeys.
"""

from __future__ import annotations

import os
import sys
import time
import psutil
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

from saleha.core.dependency_graph import dependency_graph
from saleha.core.memory_store import memory_store
from saleha.core.git_native import git_engine
from saleha.core.model_provider import default_provider


class TerminalHUD:
    """Real-time multi-quadrant terminal HUD for Saleha AI."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)
        self.console = Console()

    def generate_layout(self) -> Layout:
        """Constructs 4-panel dashboard layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        layout["left"].split_column(
            Layout(name="telemetry", ratio=1),
            Layout(name="memory", ratio=1)
        )
        layout["right"].split_column(
            Layout(name="codebase", ratio=1),
            Layout(name="hotkeys", ratio=1)
        )

        # 1. Header
        header_text = Text("⚡ SALEHA AI FRAMEWORK :: AUTONOMOUS ENGINEERING DASHBOARD ⚡", style="bold cyan")
        layout["header"].update(Panel(header_text, style="cyan on black", border_style="cyan"))

        # 2. Top-Left: System & Ollama Telemetry
        telemetry_table = Table(box=None, expand=True)
        telemetry_table.add_column("Metric", style="bold white")
        telemetry_table.add_column("Value", style="yellow")

        # CPU & RAM
        cpu_percent = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        telemetry_table.add_row("CPU Load", f"{cpu_percent}%")
        telemetry_table.add_row("RAM Usage", f"{ram.percent}% ({round(ram.used / (1024**3), 1)}GB / {round(ram.total / (1024**3), 1)}GB)")

        # Ollama status
        available_models = default_provider.list_models() if hasattr(default_provider, "list_models") else ["deepseek-r1:8b", "qwen2.5-coder:7b"]
        telemetry_table.add_row("Ollama Status", "[green]Online ●[/green]" if available_models else "[red]Offline ○[/red]")
        telemetry_table.add_row("Active Models", f"{len(available_models)} loaded ({', '.join(available_models[:2])})")

        layout["left"]["telemetry"].update(
            Panel(telemetry_table, title="[bold green]🖥️ System & LLM Telemetry[/bold green]", border_style="green")
        )

        # 3. Bottom-Left: Memory & Worktree Stats
        mem_table = Table(box=None, expand=True)
        mem_table.add_column("Property", style="bold white")
        mem_table.add_column("Count", style="magenta")

        total_entries = len(memory_store._entries) if hasattr(memory_store, "_entries") else 0
        mem_table.add_row("Long-Term Memories", f"{total_entries} vector entries")
        mem_table.add_row("Memory Compactor", "[green]Active (TF-IDF Vector)[/green]")
        mem_table.add_row("Active Worktrees", f"{len(git_engine._active_worktrees) if hasattr(git_engine, '_active_worktrees') else 0} ephemeral branches")
        mem_table.add_row("Execution Policy", "[cyan]Docker Fail-Closed + Local AST[/cyan]")

        layout["left"]["memory"].update(
            Panel(mem_table, title="[bold magenta]🧠 Agent Memory & Sandboxing[/bold magenta]", border_style="magenta")
        )

        # 4. Top-Right: Codebase Intelligence
        if not dependency_graph.files_indexed:
            dependency_graph.build_graph(root_dir=self.root_dir)

        code_table = Table(box=None, expand=True)
        code_table.add_column("Entity", style="bold white")
        code_table.add_column("Count", style="cyan")

        total_refs = sum(len(refs) for refs in dependency_graph.references.values())
        code_table.add_row("Indexed Files", f"{len(dependency_graph.files_indexed)} source files")
        code_table.add_row("AST Defined Symbols", f"{len(dependency_graph.definitions)} symbols")
        code_table.add_row("Cross-File Calls", f"{total_refs} call sites")
        
        branch = git_engine.get_current_branch() if git_engine.is_git_repo() else "N/A"
        code_table.add_row("Git Branch", f"[blue]{branch}[/blue]")

        layout["right"]["codebase"].update(
            Panel(code_table, title="[bold blue]🌐 Codebase & AST Intelligence[/bold blue]", border_style="blue")
        )

        # 5. Bottom-Right: Quick Actions & Shortcuts
        hotkeys_table = Table(box=None, expand=True)
        hotkeys_table.add_column("Command", style="bold yellow")
        hotkeys_table.add_column("Description", style="white")

        hotkeys_table.add_row("saleha fix <cmd>", "Auto-heal failing tests/builds")
        hotkeys_table.add_row("saleha search <query>", "BM25+Vector semantic search")
        hotkeys_table.add_row("saleha review --ensemble", "3-Agent consensus code review")
        hotkeys_table.add_row("saleha doctor --fix", "System diagnostic & auto-repair")
        hotkeys_table.add_row("saleha chat", "Autonomous interactive REPL")

        layout["right"]["hotkeys"].update(
            Panel(hotkeys_table, title="[bold yellow]⚡ Developer Action Shortcuts[/bold yellow]", border_style="yellow")
        )

        # 6. Footer
        footer_text = Text("Press Ctrl+C to exit HUD | Saleha AI 1.5.0 Enterprise Hardened", style="dim white")
        layout["footer"].update(Panel(footer_text, style="black on grey23", border_style="grey37"))

        return layout

    def render_once(self):
        """Renders a single snapshot of the HUD (for non-interactive CLI / tests)."""
        layout = self.generate_layout()
        self.console.print(layout)

    def run_live(self, refresh_rate: float = 1.0):
        """Runs live auto-refreshing terminal dashboard."""
        try:
            with Live(self.generate_layout(), console=self.console, screen=True, refresh_per_second=int(1.0/refresh_rate)) as live:
                while True:
                    time.sleep(refresh_rate)
                    live.update(self.generate_layout())
        except KeyboardInterrupt:
            self.console.print("\n[green]HUD stopped.[/green]")


# Global instance
terminal_hud = TerminalHUD()
