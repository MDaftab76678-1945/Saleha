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
def self_improve():
    """Autonomous self-improvement: finds an untested core module, writes and
    verifies a real test for it, commits to auto/self-improve locally. Never
    pushes to a remote -- that stays a human decision."""

@self_improve.command(name='run')
def self_improve_run():
    from saleha.core.self_improve import run_self_improvement_cycle
    result = run_self_improvement_cycle()
    color = 'green' if result.status == 'committed' else 'yellow'
    console.print(f"[bold {color}]{result.status}[/] — {result.module or '(none)'}")
    if result.status == 'committed':
        console.print(f'  branch: {result.branch}  commit: {result.commit_sha[:10]}')
    else:
        console.print(f'  {result.detail[:300]}')

@self_improve.command(name='log')
@click.option('--limit', default=20)
def self_improve_log(limit):
    from saleha.core.self_improve import read_log
    for entry in read_log(limit):
        console.print(f"  [{entry['timestamp']}] {entry['status']:18} {entry['module']}")

