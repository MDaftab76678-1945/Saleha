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

@cli.group()
def scheduler():
    """Manage cron-scheduled agent tasks. Nothing runs these automatically --
    use 'scheduler run-due' from an external cron job/Task Scheduler entry."""

@scheduler.command(name='list')
def scheduler_list():
    from saleha.core.task_scheduler import task_scheduler
    for t in task_scheduler.list_tasks():
        console.print(f'  {t.task_id}  [{t.cron_expression}]  {t.goal[:60]}  status={t.last_status}')

@scheduler.command(name='add')
@click.argument('cron_expression')
@click.argument('goal')
@click.option('--agent', default='Swarm')
def scheduler_add(cron_expression, goal, agent):
    from saleha.core.task_scheduler import task_scheduler
    t = task_scheduler.register_task(cron_expression, goal, agent)
    console.print(f'[bold green]Scheduled[/] {t.task_id}, next run: {t.next_run_timestamp}')

@scheduler.command(name='run-due')
def scheduler_run_due():
    """Executes every task whose next_run has passed. Call this periodically
    (e.g. an OS-level cron/Task Scheduler entry) -- saleha does not run a
    background loop that fires tasks on its own."""
    from saleha.core.task_scheduler import task_scheduler
    results = task_scheduler.run_due_tasks()
    if not results:
        console.print('[dim]Nothing due.[/]')
    for r in results:
        console.print(f"  {r['task_id']}: {r['status']} ({r['duration_ms']}ms)")

