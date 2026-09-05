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

@cli.group(name='git')
def git_group():
    """Git-Native operations, conventional commits, and pre-commit security hooks."""
    pass

@git_group.command(name='hook')
@click.argument('action', type=click.Choice(['install', 'uninstall', 'status']))
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def git_hook_cmd(action, as_json):
    """
    Manage Git pre-commit AST SAST security gates.
    
    Example install: saleha git hook install
    Example uninstall: saleha git hook uninstall
    """
    from saleha.core.git_hooks import hook_manager
    if action == 'install':
        res = hook_manager.install_pre_commit()
    elif action == 'uninstall':
        res = hook_manager.uninstall_pre_commit()
    else:
        git_dir = os.path.join(os.path.abspath('.'), '.git', 'hooks', 'pre-commit')
        installed = os.path.isfile(git_dir)
        res = {'installed': installed, 'hook_path': git_dir if installed else None}
    if as_json:
        click.echo(json.dumps(res, ensure_ascii=True))
        return
    if action == 'status':
        status_txt = '[bold green]Active (Installed)[/]' if res.get('installed') else '[yellow]Not Installed[/]'
        console.print(f'🛡️ Pre-Commit SAST Hook: {status_txt}')
        return
    if res.get('success'):
        console.print(f"[bold green]✅ {res.get('message')}[/]")
    else:
        console.print(f"[bold red]❌ {res.get('error')}[/]")

@git_group.command(name='status')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def git_status_cmd(as_json):
    """View current Git repository status and branch."""
    from saleha.core.git_native import git_engine
    status = git_engine.get_status_summary()
    if as_json:
        click.echo(json.dumps(status, ensure_ascii=True))
        return
    if not status.get('is_repo'):
        console.print('[bold red]Not a Git repository.[/]')
        return
    dirty_txt = '[bold red]Dirty (Uncommitted Changes)[/]' if status.get('dirty') else '[bold green]Clean[/]'
    console.print(Panel(f"[bold cyan]Branch:[/] {status.get('branch')}\n[bold cyan]Working Tree:[/] {dirty_txt}\n[bold cyan]Uncommitted Files:[/] {status.get('dirty_count')}\n" + '\n'.join([f'  • {f}' for f in status.get('files', [])]), title='[bold green]🌿 Saleha Git Status[/]', border_style='green'))

