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

@cli.group(name='mcp')
def mcp_group():
    """Universal Model Context Protocol (MCP) Multi-Platform Hub."""
    pass

@mcp_group.command(name='list')
@click.option('--category', '-c', help='Filter MCP servers by category')
def mcp_list_cmd(category: Optional[str]):
    """List all 30+ pre-configured MCP servers."""
    from saleha.core.mcp_hub import mcp_hub
    servers = mcp_hub.list_servers(category=category)
    table = Table(title='🔌 Universal Model Context Protocol (MCP) Server Hub', border_style='cyan')
    table.add_column('Server Name', style='bold cyan')
    table.add_column('Category', style='magenta')
    table.add_column('Transport', style='yellow')
    table.add_column('Description', style='white')
    for s in servers:
        table.add_row(s.name, s.category, s.transport, s.description)
    console.print(table)
    console.print(f"[dim]Total: {len(servers)} pre-configured servers. Export configs using 'saleha mcp export <platform>'.[/dim]")

@mcp_group.command(name='export')
@click.argument('platform', type=click.Choice(['cursor', 'claude', 'vscode', 'windsurf', 'zed', 'jetbrains', 'universal'], case_sensitive=False))
@click.option('--output', '-o', help='Optional custom output file path')
def mcp_export_cmd(platform: str, output: Optional[str]):
    """Export tailored MCP configuration for Cursor, Claude, VS Code, Windsurf, Zed, or JetBrains."""
    from saleha.core.mcp_hub import mcp_hub
    target_file, config_data = mcp_hub.export_config(platform, output_path=output)
    console.print(f'[bold green]✅ Exported {platform.upper()} MCP configuration to: [underline]{target_file}[/underline][/bold green]')
    console.print(Panel(json.dumps(config_data, indent=2)[:400] + '\n  ...', title=f'{platform.upper()} Configuration Snippet', border_style='cyan'))

@mcp_group.command(name='connect')
@click.argument('server_name')
def mcp_connect_cmd(server_name: str):
    """Test connection to an MCP server."""
    from saleha.core.mcp_hub import mcp_hub
    res = mcp_hub.connect_server(server_name)
    if res.get('success'):
        console.print(f"[bold green]✅ {res['message']}[/bold green]")
    else:
        console.print(f"[bold red]❌ Connection failed: {res.get('error')}[/bold red]")

@mcp_group.command(name='serve')
def mcp_serve_cmd():
    """Start Saleha's standard JSON-RPC 2.0 stdio MCP server."""
    from saleha.core.mcp_engine import MCPServer
    server = _cmds.MCPServer()
    console.print('[bold green]🚀 Saleha MCP Server running over stdio (JSON-RPC 2.0)...[/bold green]')
    server.run_stdio()

