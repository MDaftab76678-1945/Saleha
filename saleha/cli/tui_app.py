"""
Saleha CLI: Full-Screen Interactive Terminal UI Workspace (SalehaTUI)

Provides an immersive, split-screen terminal workspace (similar to Aider / OpenCodeInterpreter):
1. Left Panel: Live Multi-Agent Thought Stream, Planner steps, and User Chat.
2. Right Panel: Real-Time Unified Diff Viewer, Test Logs, and System Telemetry.
3. Bottom Bar: Double-Entry Token ROI Ledger & PBFT Consensus status.
4. Interactive Command Loop: :solve <goal>, :diff, :ledger, :consensus, :exit.
"""

import sys
import os
import time
from typing import List, Dict, Optional, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.syntax import Syntax
from rich.text import Text

from saleha.orchestrator import SalehaOrchestrator
from saleha.core.token_ledger import token_ledger
from saleha.core.swarm_consensus import swarm_consensus


class SalehaTUI:
    """Interactive full-screen Terminal User Interface for Saleha."""

    def __init__(self, model: str = "auto"):
        """Initializes the TUI workspace."""
        self.model = model
        self.console = Console()
        self.chat_history: List[str] = [
            "[bold cyan]🤖 Saleha v2.6.0 Ready.[/bold cyan] 100% Local-First Multi-Agent Platform.",
            "Type your coding goal or enter [italic yellow]:help[/italic yellow] for command shortcuts.",
        ]
        self.latest_diff: str = "# No surgical diffs active.\n# Submit a task to generate patches."
        self.latest_test_status: str = "Ready for execution."

    def build_layout(self) -> Layout:
        """Constructs the split-screen Rich layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        layout["body"].split_row(
            Layout(name="left_chat", ratio=1),
            Layout(name="right_diff", ratio=1),
        )

        # Header
        header_text = Text(f"🚀 SALEHA SOVEREIGN WORKSPACE v2.6.0  |  Model: {self.model}  |  Consensus: 2f+1 PBFT", style="bold white on blue")
        layout["header"].update(Panel(header_text, style="blue"))

        # Left Chat
        chat_content = "\n\n".join(self.chat_history[-8:])
        layout["left_chat"].update(Panel(chat_content, title="💬 Agent Interaction Stream", border_style="cyan"))

        # Right Diff & Tests
        syntax_diff = Syntax(self.latest_diff, "python", theme="monokai", line_numbers=True)
        layout["right_diff"].update(Panel(syntax_diff, title=f"⚡ Surgical Code Diff ({self.latest_test_status})", border_style="green"))

        # Footer
        summary = token_ledger.get_summary()
        footer_text = f"💰 Tokens Saved: {summary['total_tokens_saved']:,} | ROI: {summary['token_roi_percent']}% | Spend: ${summary['estimated_spend_usd']} | Commands: :solve, :clear, :exit"
        layout["footer"].update(Panel(footer_text, style="magenta"))

        return layout

    def render(self):
        """Renders the current TUI frame."""
        self.console.clear()
        self.console.print(self.build_layout())

    def run_interactive_loop(self):
        """Launches the interactive TUI prompt session."""
        self.render()
        while True:
            try:
                user_input = self.console.input("\n[bold green]saleha-tui>[/bold green] ").strip()
                if not user_input:
                    continue

                if user_input.lower() in [":exit", ":quit", "exit", "quit"]:
                    self.console.print("[bold yellow]Exiting Saleha TUI Workspace. Goodbye![/bold yellow]")
                    break

                if user_input.lower() in [":clear", "clear"]:
                    self.chat_history = ["[bold cyan]🤖 Chat history cleared.[/bold cyan]"]
                    self.render()
                    continue

                if user_input.lower() in [":help", "help"]:
                    self.chat_history.append("[bold white]Available commands:[/bold white]\n:solve <goal> - Run autonomous solver\n:clear - Clear chat\n:exit - Exit TUI")
                    self.render()
                    continue

                # Process task
                goal = user_input[7:].strip() if user_input.startswith(":solve ") else user_input
                self.chat_history.append(f"[bold yellow]👤 User:[/bold yellow] {goal}")
                self.chat_history.append("[bold cyan]🤖 Agents:[/bold cyan] Planning and analyzing problem...")
                self.latest_test_status = "Running solver..."
                self.render()

                orchestrator = SalehaOrchestrator(model=self.model, max_healing_attempts=2)
                exec_res = orchestrator.execute_task(goal)

                if exec_res.final_code:
                    self.latest_diff = exec_res.final_code[:500]
                status_str = "Passed ✅" if exec_res.success else "Failed ❌"
                self.latest_test_status = f"Status: {status_str}"
                self.chat_history.append(f"[bold cyan]🤖 Outcome:[/bold cyan] Task {status_str} ({exec_res.attempts} attempts).")
                self.render()

            except (KeyboardInterrupt, EOFError):
                break


def launch_tui(model: str = "auto"):
    """CLI launcher for Saleha TUI."""
    tui = SalehaTUI(model=model)
    tui.run_interactive_loop()


if __name__ == "__main__":
    _t = SalehaTUI(model="mock")
    _t.render()
