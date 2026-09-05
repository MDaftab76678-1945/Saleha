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

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host address to bind')
@click.option('--port', default=8000, type=int, help='Port to listen on')
@click.option('--open/--no-open', 'open_browser', default=True, help='Open in default browser')
def serve(host, port, open_browser):
    """Launch the interactive Saleha Web Studio & REST API Server."""
    console.print(Panel.fit(f'[bold cyan]🌐 URL:[/] http://{host}:{port}\n[bold cyan]🚀 Web Studio:[/] Active\n[bold cyan]📡 REST & SSE API:[/] Enabled\n[dim]Press Ctrl+C in terminal to stop server[/]', title='[bold green]🧠 Saleha Web Studio[/]', border_style='green'))
    _cmds.run_web_studio(host=host, port=port, open_browser=open_browser)

@cli.command()
@click.argument('url')
@click.option('--selector', '-s', multiple=True, help='DOM selectors to verify (e.g. "#app", ".navbar")')
@click.option('--screenshot', '-p', default=None, help='File path to save screenshot')
@click.option('--timeout', '-t', default=10, help='Page load timeout in seconds')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def browser(url, selector, screenshot, timeout, as_json):
    """
    Automated Headless Browser Testing & Verification (Playwright).
    
    Example: saleha browser http://localhost:8000
    Example with DOM check: saleha browser http://localhost:3000 -s "#root" -s "button"
    Example with screenshot: saleha browser http://localhost:8000 --screenshot ./app.png
    """
    from saleha.core.browser_runner import browser_runner
    with Progress(SpinnerColumn(), TextColumn(f'[cyan]Navigating to {url}...'), console=console) as progress:
        progress.add_task('browser', total=None)
        res = browser_runner.navigate(url=url, expected_selectors=list(selector), capture_screenshot=bool(screenshot), screenshot_path=screenshot, timeout=timeout)
    if as_json:
        click.echo(json.dumps({'success': res.success, 'url': res.url, 'status_code': res.status_code, 'title': res.title, 'console_errors': res.console_errors, 'screenshot_path': res.screenshot_path, 'dom_elements_found': res.dom_elements_found, 'load_time': res.load_time, 'backend': res.backend, 'error': res.error}, ensure_ascii=True))
        return
    status_color = 'green' if res.success else 'red'
    dom_summary = '\n'.join([f"  • {k}: {('✅ Found' if v else '❌ Missing')}" for k, v in res.dom_elements_found.items()]) if res.dom_elements_found else '  • None requested'
    error_summary = '\n'.join([f'  • {e}' for e in res.console_errors]) if res.console_errors else '  • None detected'
    console.print(Panel(f"[bold cyan]URL:[/] {res.url}\n[bold cyan]Status Code:[/] [{status_color}]{res.status_code}[/]\n[bold cyan]Title:[/] {res.title or 'N/A'}\n[bold cyan]Backend:[/] {res.backend}\n[bold cyan]Load Time:[/] {res.load_time}s\n[bold yellow]DOM Elements:[/]\n{dom_summary}\n[bold red]Console Errors:[/]\n{error_summary}" + (f'\n[bold green]Screenshot:[/] {res.screenshot_path}' if res.screenshot_path else ''), title=f'[{status_color}]🌐 Saleha Headless Browser Verification[/]', border_style=status_color))

@cli.command(name='server')
@click.option('--port', default=8000, help='Port to bind distributed swarm server')
@click.option('--dry-run', is_flag=True, help='Initialize and test cluster telemetry without blocking')
def server_cmd(port, dry_run):
    """
    Start Distributed GPU Swarm Server for team-wide shared LLM compute.
    
    Example: saleha server --port 8000
    """
    from saleha.core.distributed_server import distributed_server
    distributed_server.port = port
    console.print(f'[bold cyan]🖥️ Starting Saleha Distributed Swarm Server on:[/] [green]http://127.0.0.1:{port}[/]')
    telem = distributed_server.get_cluster_telemetry()
    console.print(f"[dim]Status: {telem['server_status']} | GPU Pool: {telem['gpu_pool']}[/]\n")
    if not dry_run:
        console.print('[yellow]Server daemon initialized. Press Ctrl+C to terminate.[/]')

@cli.command(name='web')
@click.option('--port', default=8000, help='Port to run Web Studio on (default: 8000)')
@click.option('--host', default='127.0.0.1', help='Host to bind Web Studio (default: 127.0.0.1)')
@click.option('--no-browser', is_flag=True, default=False, help='Do not automatically open browser')
def web_cmd(port: int, host: str, no_browser: bool):
    """
    Launch Saleha Web Studio 2.0 Glassmorphic IDE & REST API Server.
    
    Example: saleha web --port 8000
    """
    from saleha.server.web_server import run_web_studio
    _cmds.run_web_studio(host=host, port=port, open_browser=not no_browser)

@cli.command(name='desktop')
@click.option('--port', '-p', default=0, help='Custom HTTP port (0 for auto-assign)')
@click.option('--browser/--no-browser', default=True, help='Launch native browser-app window')
def desktop_cmd(port, browser):
    """
    Launch Saleha Native Desktop GUI Application.
    
    Example: saleha desktop
    """
    from saleha.desktop.app import SalehaDesktopApp
    app = SalehaDesktopApp(port=port)
    assigned_port = app.start_server()
    app_url = app.get_app_url()
    console.print(f'[bold green]🖥️ Saleha AI Desktop v2.0 running![/]')
    console.print(f'  • URL: [bold cyan]{app_url}[/]')
    console.print(f'  • Port: [yellow]{assigned_port}[/]')
    console.print(f'  • Token: [dim]{app.token}[/]\n')
    if browser:
        console.print('[cyan]Launching native desktop GUI window...[/]')
        app.launch_window(app_url)
    console.print('[dim]Press Ctrl+C to stop the desktop application.[/]')
    try:
        while app.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        console.print('\n[yellow]Desktop application stopped.[/]')

