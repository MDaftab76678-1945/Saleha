"""Auto-extracted from the former monolithic saleha/cli/commands.py.

Imports `cli` to register commands against the same Click group, and `_cmds`
(the package module itself) so any reference to a lazily-imported name (see
_LAZY_IMPORT_MAP in __init__.py) or a shared helper resolves through the
original module -- this keeps mock.patch("saleha.cli.commands.X") working
for tests that patch those names, and preserves the PEP 562 lazy-loading
behavior for whatever this file's commands use.
"""
import click
from saleha.cli.commands import cli, console
from saleha.cli import commands as _cmds

from typing import Optional, Tuple, List, Dict, Any, Callable, Union, Set, TYPE_CHECKING
import os
import sys
import re
import time
import json
import io
import subprocess
import contextlib
from pathlib import Path
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
from saleha import __version__

@cli.command(name='memory-project')
@click.option('--project', default='current', help='Project identifier')
@click.option('--recall', 'query', default=None, help='Search memory query')
@click.option('--remember', 'new_fact', default=None, help='Store new memory fact')
@click.option('--cat', default='fact', help='Memory category (fact/decision/fix)')
def memory_project_cmd(project, query, new_fact, cat):
    """
    Manage Per-Project Persistent Agent Memory (Decisions, Fixes, Facts).
    
    Example: saleha memory-project --remember "Use SQLite for session" --cat decision
    """
    from saleha.core.project_memory import get_project_memory
    mem = get_project_memory(project)
    if new_fact:
        entry = mem.remember(new_fact, category=cat)
        console.print(f'[bold green]🧠 Remembered for [{project}]:[/] {entry.content} [dim]({entry.category})[/]')
        return
    if query:
        results = mem.recall(query)
        if not results:
            console.print(f"[yellow]No memories found matching '{query}' in project '{project}'.[/]")
            return
        console.print(f"[bold cyan]🧠 Memories for [{project}] matching '{query}':[/]")
        for r in results:
            console.print(f'  • [[bold yellow]{r.category}[/]] {r.content} [dim]({r.timestamp})[/]')
        return
    stats = mem.stats()
    console.print(f'[bold cyan]🧠 Project Memory Stats for [{project}]:[/]')
    console.print(f"  Total Entries: [bold green]{stats['total_entries']}[/]")
    for c, count in stats.get('categories', {}).items():
        console.print(f'    • {c}: {count}')

@cli.command(name='context-board')
def context_board_cmd():
    """
    Inspect the live Swarm Shared Context Blackboard.
    
    Example: saleha context-board
    """
    from saleha.core.context_board import global_context_board
    console.print(Panel('[bold magenta]📋 Saleha Swarm Context Blackboard[/bold magenta]', border_style='magenta'))
    console.print(Markdown(global_context_board.export_markdown()))

