"""
Saleha CLI: Interactive Terminal Side-by-Side Diff Reviewer

Renders rich, colorized diff previews with syntax highlighting and provides
interactive keyboard confirmation before committing surgical edits to disk.
"""

import difflib
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt

console = Console(safe_box=True)


@dataclass
class DiffChunk:
    file_path: str
    original_code: str
    new_code: str


class InteractiveDiffReviewer:
    """Renders side-by-side terminal diffs and handles interactive developer confirmation."""

    def __init__(self, console_instance: Optional[Console] = None):
        self.console = console_instance or console

    def render_diff_panel(self, file_path: str, old_code: str, new_code: str) -> None:
        """Displays a clean, colored unified and chunk comparison panel."""
        old_lines = old_code.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3
        ))

        if not diff:
            self.console.print(f"[dim]No changes detected in {file_path}[/]")
            return

        diff_text = "".join(diff)
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)

        self.console.print(Panel(
            syntax,
            title=f"[bold cyan]📝 Diff Review: {file_path}[/]",
            subtitle="[green]+ additions[/] | [red]- deletions[/]",
            border_style="cyan"
        ))

    def prompt_review(self, file_path: str, old_code: str, new_code: str, auto_approve: bool = False) -> bool:
        """Renders diff and prompts developer to accept or reject."""
        self.render_diff_panel(file_path, old_code, new_code)
        if auto_approve:
            return True

        choice = Prompt.ask(
            f"[bold yellow]Apply changes to {file_path}?[/] [y/n/q]",
            choices=["y", "n", "q"],
            default="y"
        )
        return choice == "y"


# Global default instance
diff_reviewer = InteractiveDiffReviewer()
