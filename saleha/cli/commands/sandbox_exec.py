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
@click.argument('target_file', type=click.Path(exists=True, dir_okay=False))
@click.option('--deps', '-d', default='', help='Third-party packages to install in sandbox (e.g. "pydantic requests")')
@click.option('--timeout', '-t', default=30, type=int, help='Sandbox execution timeout in seconds')
@click.option('--docker', is_flag=True, help='Execute inside isolated Docker container with memory/CPU cgroups')
@click.option('--lang', default='python', help='Language runtime (python, javascript, go)')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def sandbox(target_file, deps, timeout, docker, lang, as_json):
    """Execute a script inside an isolated ephemeral virtual environment or Docker sandbox."""
    with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
        file_code = f.read()
    if docker:
        docker_runner = _cmds.DockerSandboxRunner()
        with contextlib.redirect_stdout(io.StringIO()) if as_json else contextlib.nullcontext():
            result = docker_runner.run_code(code=file_code, language=lang, timeout=timeout)
    else:
        dep_list = [d.strip() for d in re.split('[\\s,]+', deps) if d.strip()]
        runner = _cmds.SandboxRunner(default_timeout=timeout)
        with contextlib.redirect_stdout(io.StringIO()) if as_json else contextlib.nullcontext():
            result = runner.run_in_sandbox(script_code_or_file=target_file, dependencies=dep_list, timeout=timeout)
    if as_json:
        payload = {'success': result.success, 'exit_code': result.exit_code, 'execution_time': round(result.execution_time, 3), 'installed_packages': result.installed_packages, 'output': result.output, 'error': result.error, 'blocked': result.blocked}
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    mode_label = 'Docker Container' if docker else 'VirtualEnv'
    console.print(Panel.fit(f'[bold cyan]📄 Target File:[/] {target_file}\n[bold cyan]🛡️ Mode:[/] {mode_label} Sandbox\n[bold cyan]⏱️ Timeout:[/] {timeout}s', title='[bold green]📦 Isolated Sandbox Execution[/]', border_style='green'))
    if result.blocked:
        console.print(Panel(f'[bold red]🚫 Execution Blocked:[/] {result.block_reason}', border_style='red'))
        return
    if result.success:
        console.print(Panel(f'[bold green]✅ Sandbox Execution Successful[/] in {result.execution_time:.2f}s (Exit code: {result.exit_code})', border_style='green'))
        if result.output:
            console.print('\n[bold cyan]📤 Standard Output:[/]')
            console.print(result.output)
    else:
        console.print(Panel(f'[bold red]❌ Sandbox Execution Failed[/] in {result.execution_time:.2f}s (Exit code: {result.exit_code})\nError: {result.error}', border_style='red'))

@cli.command(name='exec')
@click.argument('filepath')
@click.option('--lang', '-l', default=None, help='Explicit language (python, javascript, typescript, go, java, rust)')
@click.option('--timeout', '-t', default=15, help='Execution timeout in seconds')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def exec_code(filepath, lang, timeout, as_json):
    """
    Execute code in multi-language sandbox with pre-execution AST SAST security gates.
    
    Supports: Python (.py), Node.js (.js), TypeScript (.ts), Go (.go), Java (.java), Rust (.rs)
    
    Example: saleha exec app.py
    Example JS: saleha exec server.js
    Example Go: saleha exec main.go
    """
    from saleha.core.polyglot_executor import polyglot_executor
    if not os.path.isfile(filepath):
        console.print(f"[bold red]Error:[/] File '{filepath}' not found.")
        raise click.exceptions.Exit(1)
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    polyglot_executor.timeout = timeout
    res = polyglot_executor.execute(code, language=lang, filename=os.path.basename(filepath))
    if as_json:
        click.echo(json.dumps({'success': res.success, 'language': res.language, 'exit_code': res.exit_code, 'output': res.output, 'error': res.error, 'blocked': res.blocked, 'block_reason': res.block_reason, 'execution_time': res.execution_time}, ensure_ascii=True))
        return
    if res.blocked:
        console.print(Panel(f'[bold red]🚫 Execution Blocked by SAST Gate[/]\n\n[yellow]Reason:[/] {res.block_reason}', title='[bold red]Security Block[/]', border_style='red'))
        raise click.exceptions.Exit(1)
    status_color = 'green' if res.success else 'red'
    output_content = res.output.strip() or '(No stdout output)'
    error_content = f'\n[bold red]Stderr/Error:[/]\n{res.error.strip()}' if res.error.strip() else ''
    console.print(Panel(f'[bold cyan]Language:[/] {res.language}\n[bold cyan]Exit Code:[/] [{status_color}]{res.exit_code}[/]\n[bold cyan]Time:[/] {res.execution_time}s\n\n[bold green]Stdout Output:[/]\n{output_content}{error_content}', title=f'[{status_color}]⚡ Saleha Polyglot Execution ({res.language})[/]', border_style=status_color))

@cli.command(name='sidecar')
@click.option('--host', default='127.0.0.1', help='Host address')
@click.option('--port', default=7890, type=int, help='Port to serve')
@click.option('--open/--no-open', 'open_browser', default=True, help='Open in browser')
def sidecar_cmd(host, port, open_browser):
    """Launch the floating desktop AI companion daemon on localhost:7890."""
    console.print(Panel(f'[bold cyan]URL:[/] http://{host}:{port}\n[bold cyan]Service:[/] Floating Desktop Sidecar Companion\n[dim]Press Ctrl+C in terminal to stop daemon[/]', title='[bold green]🪟 Saleha Desktop Sidecar Active[/]', border_style='green'))
    from saleha.core.sidecar_daemon import sidecar_daemon
    sidecar_daemon.run(host=host, port=port, open_browser=open_browser)

@cli.command(name='watch')
@click.argument('directory', default='.')
@click.option('--debounce', default=0.3, type=float, help='Debounce seconds for save events')
def watch_cmd(directory, debounce):
    """
    Watch workspace files in real-time and display live AST symbol updates & blast-radius alerts.
    
    Example: saleha watch ./src
    """
    from saleha.core.repo_watcher import RepoWatcher
    watcher = RepoWatcher(root_dir=directory, poll_interval=0.5, debounce_sec=debounce)
    watcher.initialize()
    console.print(Panel(f'[bold cyan]Watching Workspace:[/] {os.path.abspath(directory)}\n[dim]Live AST indexer active. Save any file in your IDE to see instant blast-radius traces.[/]\n[dim]Press Ctrl+C to stop watching.[/]', title='[bold green]👁️ Saleha Live Repo Watcher[/]', border_style='green'))

    def on_event(ev):
        color = 'green' if ev.change_type == 'created' else 'yellow' if ev.change_type == 'modified' else 'red'
        syms = f" [cyan](Symbols: {', '.join(ev.symbols_defined[:4])})[/]" if ev.symbols_defined else ''
        console.print(f'[{color}]⚡ {ev.change_type.upper()}:[/] [bold white]{ev.file_path}[/]{syms}')
        if ev.impacted_downstream_files:
            console.print(f"   [bold magenta]↳ ⚠️ Downstream Blast Radius ({len(ev.impacted_downstream_files)} files):[/] [yellow]{', '.join(ev.impacted_downstream_files[:4])}[/]")
    watcher.on_change(on_event)
    watcher.start_background()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        watcher.stop()
        console.print('\n[dim]Watcher stopped.[/]')

@cli.command(name='sandbox')
@click.argument('script_path')
@click.option('--timeout', '-t', default=15, help='Timeout in seconds')
@click.option('--memory', '-m', default='256m', help='Memory limit (e.g. 512m)')
@click.option('--json', 'json_output', is_flag=True, help='Output result as JSON')
def sandbox_cmd(script_path, timeout, memory, json_output):
    """
    Execute code inside a hardened isolated security sandbox (Docker / process sandbox).
    
    Example: saleha sandbox script.py --timeout 10
    """
    from saleha.core.hardened_sandbox import hardened_sandbox
    if not os.path.isfile(script_path):
        if json_output:
            click.echo(json.dumps({'success': False, 'error': f'File not found: {script_path}', 'output': ''}))
        else:
            console.print(f'[bold red]Error:[/] File not found: {script_path}')
        return
    with open(script_path, 'r', encoding='utf-8') as f:
        code = f.read()
    try:
        res = hardened_sandbox.execute_code(code, timeout=timeout, memory_limit=memory)
    except Exception as ex:
        from saleha.core.hardened_sandbox import HardenedExecutionResult
        res = HardenedExecutionResult(success=False, output='', error=str(ex), sandbox_tier='fallback')
    if json_output:
        click.echo(json.dumps({'success': res.success, 'output': res.output, 'error': res.error, 'sandbox_tier': res.sandbox_tier}))
        return
    console.print(f'[bold cyan]🛡️ Executing in Hardened Sandbox:[/] [yellow]{script_path}[/]')
    if res.success:
        console.print(f'[bold green]✅ Sandbox Execution Succeeded (Tier: {res.sandbox_tier}):[/]')
        console.print(res.output)
    else:
        console.print(f'[bold red]❌ Sandbox Execution Failed (Tier: {res.sandbox_tier}):[/]')
        console.print(res.error)

@cli.command(name='sandbox-run')
@click.argument('code', required=True)
def sandbox_run_cmd(code: str):
    """
    Execute Python code in an isolated containment sandbox.
    
    Example: saleha sandbox-run "print(2+2)"
    """
    from saleha.core.sandbox_runner import sandbox_runner
    res = sandbox_runner.run_python_code(code)
    col = 'green' if res.success else 'red'
    console.print(Panel(f'[bold {col}]📦 Sandbox Execution Result[/bold {col}]\n{res.summary}\n[bold white]Output:[/bold white]\n{res.stdout or res.stderr}', border_style=col))

