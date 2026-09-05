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

@cli.group(name='hook')
def hook_group():
    """
    Git Pre-Commit & Security Guardrail Hooks.
    """
    pass

@hook_group.command(name='install')
def hook_install_cmd():
    """
    Install Git pre-commit hook in .git/hooks.
    
    Example: saleha hook install
    """
    from saleha.core.git_hooks import git_hook_manager
    ok, msg = git_hook_manager.install_hooks()
    if ok:
        console.print(f'[bold green]✅ {msg}[/]')
    else:
        console.print(f'[bold red]❌ {msg}[/]')

@hook_group.command(name='uninstall')
def hook_uninstall_cmd():
    """
    Remove Git pre-commit hook.
    
    Example: saleha hook uninstall
    """
    from saleha.core.git_hooks import git_hook_manager
    ok, msg = git_hook_manager.uninstall_hooks()
    console.print(f'[yellow]{msg}[/]')

@hook_group.command(name='run')
def hook_run_cmd():
    """
    Execute pre-commit security and AST syntax scan on staged files.
    
    Example: saleha hook run
    """
    from saleha.core.git_hooks import git_hook_manager
    passed, errors = git_hook_manager.run_pre_commit_check()
    if passed:
        console.print('[bold green]✅ Pre-commit verification passed. 0 syntax errors or secret leaks.[/]')
    else:
        console.print('[bold red]❌ Pre-commit validation failed:[/]')
        for e in errors:
            console.print(f'  • [red]{e}[/]')
        import sys
        sys.exit(1)

