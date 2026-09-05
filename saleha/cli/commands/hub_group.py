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

@cli.group(name='hub')
def hub_group():
    """Discover, install, and manage community plugins and skills."""
    pass

@hub_group.command(name='list')
def hub_list_cmd():
    """List available plugins in the Saleha Hub registry."""
    from saleha.core.plugin_hub import plugin_hub
    plugins = plugin_hub.list_available_hub_plugins()
    table = Table(title='🧩 Saleha Hub: Community Plugins Catalog', border_style='cyan')
    table.add_column('Plugin Name', style='bold white')
    table.add_column('Version', style='bold cyan')
    table.add_column('Author', style='italic white')
    table.add_column('Description', style='white')
    for p in plugins:
        table.add_row(p.name, p.version, p.author, p.description)
    console.print(table)

@hub_group.command(name='install')
@click.argument('plugin_name', required=True)
def hub_install_cmd(plugin_name: str):
    """Install a community plugin from the Hub."""
    from saleha.core.plugin_hub import plugin_hub
    ok = plugin_hub.install_plugin(plugin_name)
    if ok:
        console.print(f"[bold green]✅ Plugin '{plugin_name}' installed and active![/bold green]")
    else:
        console.print(f"[bold red]❌ Plugin '{plugin_name}' not found in Hub catalog.[/bold red]")

