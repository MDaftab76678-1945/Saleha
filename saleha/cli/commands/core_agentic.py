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
@click.argument('goal', required=False)
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--profile', '-p', default=None, help='Agent profile to adopt (e.g. security_engineer, sde)')
@click.option('--max-attempts', default=3, type=click.IntRange(1, 10), help='Maximum self-healing attempts')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed logs')
@click.option('--execute', '-x', is_flag=True, help='Auto-execute generated code')
@click.option('--commit', '-c', is_flag=True, help='Create atomic conventional git commit upon success')
@click.option('--context-dir', '-cd', default=None, type=click.Path(exists=True, file_okay=False), help='Pack task-relevant repo context (Aider-style map) into the coder prompt')
@click.option('--tests', '-t', is_flag=True, help='Generate a unittest suite and use REAL test execution in the healing loop')
@click.option('--resume', '-r', is_flag=True, help='Resume the last interrupted session from its checkpoint')
@click.option('--stream', is_flag=True, help='Stream coder tokens live in the terminal')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def run(goal, model, profile, max_attempts, verbose, execute, commit, context_dir, tests, resume, stream, as_json):
    """
    Full self-healing pipeline: Plan -> Code -> Test -> Fix -> Execute
    
    Example: saleha run "Create a REST API"
    Example with profile: saleha run "Implement distributed lock" -p sde
    Example with execution: saleha run -x "Create a function that prints hello"
    Example with git commit: saleha run -c "Build rate limiter"
    Example with repo context: saleha run "Add retry logic" --context-dir ./src
    Example with real tests: saleha run "Build roman numerals converter" --tests
    Resume after crash: saleha run --resume
    """
    from saleha.core.code_executor import CodeExecutor
    if resume and goal:
        raise click.UsageError('--resume ke saath GOAL mat do -- saved session ka goal use hota hai.')
    if not goal and (not resume):
        raise click.UsageError('GOAL zaroori hai (ya --resume use karein).')
    if not goal:
        goal = ''
    orchestrator = _cmds.SalehaOrchestrator(model=model, max_healing_attempts=max_attempts, profile=profile)
    if as_json:
        with contextlib.redirect_stdout(io.StringIO()):
            result = orchestrator.execute_task(goal, profile=profile, auto_commit=commit, context_dir=context_dir, generate_tests=tests, resume_session=resume)
    else:
        profile_info = f'\n[bold cyan]🎭 Profile:[/] {profile}' if profile else ''
        context_info = f'\n[bold cyan]📦 Repo Context:[/] {context_dir}' if context_dir else ''
        tests_info = '\n[bold cyan]🧪 Real Tests:[/] enabled' if tests else ''
        resume_info = '\n[bold cyan]⏯️ Mode:[/] RESUME last checkpoint' if resume else ''
        console.print(Panel.fit(f"[bold cyan]🎯 Goal:[/] {goal or '(from checkpoint)'}\n[bold cyan]🤖 Model:[/] {model}{profile_info}{context_info}{tests_info}{resume_info}\n[bold cyan]🔄 Max Attempts:[/] {max_attempts}", title='[bold green]Saleha Orchestrator[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console, disable=stream) as progress:
            progress.add_task('[cyan]Processing...', total=None)
            _cb = None
            if stream:

                def _cb(token: str):
                    console.print(token, end='')
            result = orchestrator.execute_task(goal, profile=profile, auto_commit=commit, context_dir=context_dir, generate_tests=tests, resume_session=resume, on_token=_cb)
            if stream:
                console.print('\n[dim]── stream end ──[/]')
    if as_json:
        payload = {'success': result.success, 'final_code': result.final_code, 'attempts': result.attempts, 'profile_used': getattr(result, 'profile_used', ''), 'log': result.log,
                   'verified': getattr(result, 'verified', False),
                   'unverified_reason': getattr(result, 'unverified_reason', '')}
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    console.print()
    if result.success:
        console.print(Panel(f'[bold green]✅ SUCCESS[/] in {result.attempts} attempt(s)', border_style='green'))
        # `verified` is a stronger claim than `success`: it means the code was
        # actually executed and ran clean. A caveat must be shown, not implied.
        _reason = getattr(result, 'unverified_reason', '')
        if _reason:
            console.print(f'[yellow]⚠ {_reason}[/]')
        console.print('\n[bold cyan]📝 Generated Code:[/]')
        syntax = Syntax(result.final_code, 'python', theme='monokai', line_numbers=True)
        console.print(syntax)
        if execute:
            console.print('\n[bold yellow]🚀 Executing Code...[/]')
            executor = CodeExecutor()
            exec_result = executor.execute(result.final_code)
            if exec_result.success:
                console.print(Panel('[bold green]✅ Execution Successful[/]', border_style='green'))
                if exec_result.output:
                    console.print('\n[bold cyan]📤 Output:[/]')
                    console.print(exec_result.output)
            else:
                console.print(Panel(f'[bold red]❌ Execution Failed[/]', border_style='red'))
                if exec_result.error:
                    console.print(f'\n[red]Error:[/] {exec_result.error}')
    else:
        # A goal too vague to act on is a question, not a failure. Rendering it
        # as "❌ FAILED after 0 attempt(s)" hid the one thing the user could do
        # about it -- the question itself only appeared under --verbose.
        if '❓' in (result.log or ''):
            ask = result.log[result.log.index('❓'):].strip()
            console.print(Panel(ask, title='[bold yellow]Need one detail[/]',
                                border_style='yellow'))
        else:
            console.print(Panel(f'[bold red]❌ FAILED[/] after {result.attempts} attempt(s)', border_style='red'))
    if verbose:
        console.print('\n[bold yellow]📜 Execution Log:[/]')
        console.print(result.log)

@cli.command()
@click.argument('goal')
@click.option('--dir', 'root_dir', default='.', type=click.Path(exists=True, file_okay=False), help='Repository root the agent operates in')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--max-steps', default=12, type=click.IntRange(1, 40), help='Maximum think-act steps')
@click.option('--write', is_flag=True, help='Allow write_file tool (still gated by SALEHA_APPROVAL)')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable transcript')
def agent(goal, root_dir, model, max_steps, write, as_json):
    """Autonomous agent that thinks, uses tools, and investigates a repo.

    Example: saleha agent "find all API endpoints missing auth checks" --dir ./src
    """
    from saleha.core.agentic_loop import AgentLoop
    from saleha.agents.base_agent import BaseAgent
    console.print(Panel.fit(f"[bold cyan]🎯 Goal:[/] {goal}\n[bold cyan]📁 Root:[/] {os.path.abspath(root_dir)}\n[bold cyan]🔧 Tools:[/] list_dir, read_file, search_repo, run_code{(', write_file' if write else '')}\n[bold cyan]🔁 Max Steps:[/] {max_steps}", title='[bold green]🤖 Saleha Autonomous Agent[/]', border_style='green'))
    loop = _cmds.AgentLoop(agent=_cmds.BaseAgent(role='Agent', model=model), root_dir=root_dir, max_steps=max_steps, allow_write=write)
    result = loop.run(goal, on_event=lambda ev: None if as_json else console.print(f"[dim]step {ev.get('step')}[/] [cyan]{ev.get('action')}[/] -> {_cmds._one_line(ev.get('observation', ''))}"))
    if as_json:
        click.echo(json.dumps({'success': result.success, 'final_message': result.final_message, 'error': result.error, 'steps': [{'step': s.step, 'action': s.action, 'args': s.args_preview, 'observation': s.observation[:500]} for s in result.steps]}, ensure_ascii=True))
    else:
        console.print(Panel(result.final_message or result.error, title='[green]✅ Agent Summary[/]' if result.success else '[red]❌ Agent Stopped[/]', border_style='green' if result.success else 'red'))
        console.print(f'[dim]{len(result.steps)} step(s) used[/]')
    if not result.success:
        raise click.exceptions.Exit(1)

@cli.command()
@click.argument('goal')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def plan(goal, model, as_json):
    """
    Generate task plan only (no code generation)
    
    Example: saleha plan "Build a web scraper"
    """
    planner = _cmds.PlannerAgent(model=model)
    if as_json:
        with contextlib.redirect_stdout(io.StringIO()):
            result = planner.create_plan(goal)
    else:
        console.print(Panel.fit(f'[bold cyan]🎯 Goal:[/] {goal}', title='[bold green]Saleha Planner[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
            progress.add_task('[cyan]Planning...', total=None)
            result = planner.create_plan(goal)
    if as_json:
        click.echo(json.dumps({'success': result.success, 'steps': result.steps, 'recommendation': result.recommendation, 'error': result.raw_response if not result.success else ''}, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    console.print()
    if result.success:
        console.print(Panel(f'[bold green]✅ Plan Generated[/] (Recommendation: {result.recommendation})', border_style='green'))
        console.print('\n[bold cyan]📋 Plan Steps:[/]')
        for i, step in enumerate(result.steps, 1):
            console.print(f'  [yellow]{i}.[/] {step}')
    else:
        console.print(Panel(f'[bold red]❌ Planning Failed[/]', border_style='red'))
        console.print(result.raw_response)

@cli.command()
@click.argument('task')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
@click.option('--output', type=click.Path(dir_okay=False), help='Write generated code to a file')
def code(task, model, as_json, output):
    """
    Generate code for a specific task
    
    Example: saleha code "Create a function to sort a list"
    """
    coder = _cmds.CoderAgent(model=model)
    if as_json:
        with contextlib.redirect_stdout(io.StringIO()):
            result = coder.generate_code(task)
    else:
        console.print(Panel.fit(f'[bold cyan]💻 Task:[/] {task}', title='[bold green]Saleha Coder[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
            progress.add_task('[cyan]Generating code...', total=None)
            result = coder.generate_code(task)
    if as_json:
        saved_to = ''
        if output and result.success:
            validation = _cmds.TesterAgent().test_code(result.code)
            if validation.passed:
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(result.code + '\n')
                saved_to = output
            else:
                result.success = False
                result.error = f'{validation.error_type}: {validation.error_message}'
        click.echo(json.dumps({'success': result.success, 'code': result.code, 'error': result.error, 'attempts': result.attempts, 'model_used': result.model_used, 'saved_to': saved_to}, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    console.print()
    if result.success:
        console.print(Panel(f'[bold green]✅ Code Generated[/] in {result.attempts} attempt(s)', border_style='green'))
        console.print('\n[bold cyan]📝 Code:[/]')
        syntax = Syntax(result.code, 'python', theme='monokai', line_numbers=True)
        console.print(syntax)
        if output:
            validation = _cmds.TesterAgent().test_code(result.code)
            if validation.passed:
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(result.code + '\n')
                console.print(f'\n[bold green]✅ Saved generated code to:[/] {output}')
            else:
                console.print(Panel(f'[bold red]❌ Save cancelled[/] - generated code failed validation\n{validation.error_type}: {validation.error_message}', border_style='red'))
    else:
        console.print(Panel(f'[bold red]❌ Code Generation Failed[/]', border_style='red'))
        console.print(result.error)

@cli.command()
@click.argument('question')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def ask(question, model, as_json):
    """Ask Saleha a normal question without starting the interactive shell."""
    agent = _cmds.BaseAgent(role='Assistant', model=model)
    result = agent.think(question)
    if as_json:
        payload = {'success': result.success, 'content': result.content, 'error': result.error_message, 'model_used': result.model_used, 'response_time': result.response_time}
        click.echo(json.dumps(payload, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    if result.success:
        console.print(result.content)
    else:
        console.print(f'[red]Error:[/] {result.error_message}')
        raise click.exceptions.Exit(1)

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def agents(as_json):
    """Show dynamic agent profiles loaded from saleha/skills/."""
    _cmds.profile_registry.reload()
    loaded_profiles = _cmds.profile_registry.list_profiles()
    if not loaded_profiles:
        if as_json:
            click.echo(json.dumps({'profiles': []}, ensure_ascii=False))
            return
        console.print('[yellow]No agent profiles are currently loaded.[/]')
        return
    if as_json:
        click.echo(json.dumps({'profiles': [{'id': p.id, 'name': p.name, 'version': p.version, 'goals': p.goals, 'tools': p.allowed_tools, 'source_file': os.path.basename(p.source_file)} for p in loaded_profiles]}, ensure_ascii=False))
        return
    table = Table(title='🎭 Loaded Agent Profiles', show_header=True, header_style='bold magenta')
    table.add_column('ID', style='cyan')
    table.add_column('Role Name', style='green')
    table.add_column('Ver', justify='center', style='dim')
    table.add_column('Goals / Summary', style='yellow')
    table.add_column('File', style='dim')
    for p in sorted(loaded_profiles, key=lambda x: x.id):
        summary = p.goals[0] if p.goals else p.system_prompt[:50] + '...' if p.system_prompt else '-'
        table.add_row(p.id, p.name, p.version, summary[:60], os.path.basename(p.source_file))
    console.print(table)

@cli.command()
@click.option('--profile', '-p', default=None, help='Initial agent profile (e.g. architect, sde, security)')
@click.option('--model', '-m', default='auto', help='Model to use')
def chat(profile, model):
    """Start an interactive pair-programming shell with Saleha agents."""
    _cmds.start_repl(initial_profile=profile, model=model)

@cli.command()
@click.option('--profile', '-p', default=None, help='Initial agent profile (e.g. architect, sde, security)')
@click.option('--model', '-m', default='auto', help='Model to use')
def repl(profile, model):
    """Alias for 'saleha chat'."""
    _cmds.start_repl(initial_profile=profile, model=model)

@cli.command()
@click.argument('goal')
@click.option('--dir', 'root_dir', default='.', type=click.Path(exists=True, file_okay=False), help='Target repository root (default: current dir)')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--apply', is_flag=True, help='Actually write changes (default: dry-run plan only)')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable edit plan')
def edit(goal, root_dir, model, apply, as_json):
    """Plan (and optionally apply) multi-file edits across an existing repo.

    Example dry-run:  saleha edit "add retry logic to API calls" --dir ./src
    Example apply:    saleha edit "rename helper.py to utils" --dir . --apply
    """
    from saleha.core.multi_file_editor import MultiFileEditor
    coder = _cmds.CoderAgent(model=model)
    editor = MultiFileEditor(coder_agent=coder, root_dir=root_dir)
    mode_label = '[bold red]APPLY[/]' if apply else '[bold yellow]DRY-RUN[/]'
    console.print(Panel.fit(f'[bold cyan]🎯 Goal:[/] {goal}\n[bold cyan]📁 Root:[/] {os.path.abspath(root_dir)}\n[bold cyan]⚙️ Mode:[/] {mode_label}', title='[bold green]✏️ Saleha Multi-File Editor[/]', border_style='green'))
    result = editor.edit(goal, apply=apply)
    if as_json:
        click.echo(json.dumps({'success': result.success, 'applied': result.applied, 'rolled_back': result.rolled_back, 'errors': result.errors, 'edits': [{'path': e.path, 'action': e.action, 'lines': e.lines_changed} for e in result.edits]}, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    if result.edits:
        table = Table(title=f'Edit Plan ({len(result.edits)} file(s))')
        table.add_column('Action', style='yellow')
        table.add_column('Path', style='cyan')
        table.add_column('Lines', justify='right')
        for e in result.edits:
            table.add_row(e.action, e.path, str(e.lines_changed))
        console.print(table)
        from rich.syntax import Syntax as _Syntax
        for e in result.edits:
            if e.diff:
                console.print(f'\n[bold cyan]📄 Diff: {e.path}[/]')
                console.print(_Syntax(e.diff, 'diff', theme='monokai'))
    if result.success and result.applied:
        console.print(f'[green]✅ {len(result.edits)} file(s) written atomically.[/]')
    elif result.success:
        console.print('[yellow]Dry-run only. Re-run with [bold]--apply[/] to write changes.[/]')
    else:
        for err in result.errors[:6]:
            console.print(f'[red]• {err}[/]')
        if result.rolled_back:
            console.print('[red]↩️ Changes rolled back -- disk untouched.[/]')
        raise click.exceptions.Exit(1)

@cli.command(name='profile')
@click.argument('code_snippet')
def profile_cmd(code_snippet):
    """
    Profile execution latency, memory footprint, and GC overhead.
    
    Example: saleha profile "sum([i**2 for i in range(100000)])"
    """
    from saleha.core.performance_profiler import performance_profiler
    console.print(f'[bold cyan]⏱️ Profiling snippet:[/] [yellow]{code_snippet}[/]')

    def target_exec():
        exec(code_snippet, {})
    _, m = performance_profiler.profile_callable(target_exec)
    if m.success:
        console.print(f'\n[bold green]✅ Execution Profile Completed:[/]')
        console.print(f'  • Duration: [cyan]{m.duration_ms} ms[/]')
        console.print(f'  • Peak Memory: [yellow]{m.peak_memory_mb} MB[/]')
        console.print(f'  • Current Memory: {m.current_memory_mb} MB')
        console.print(f'  • GC Collections: {m.gc_collections}\n')
    else:
        console.print(f'[bold red]❌ Execution failed:[/] {m.error}\n')

@cli.command()
@click.option('--live', is_flag=True, help='Run auto-refreshing live dashboard')
@click.option('--refresh', default=2.0, help='Refresh interval in seconds (for live mode)')
def dashboard(live, refresh):
    """Render the Saleha multi-agent operations dashboard."""
    if live:
        _cmds.run_live_dashboard(refresh_seconds=refresh)
    else:
        _cmds.render_dashboard()

@cli.command()
@click.option('--live', is_flag=True, help='Run auto-refreshing live dashboard')
@click.option('--refresh', default=2.0, help='Refresh interval in seconds (for live mode)')
def ui(live, refresh):
    """Alias for 'saleha dashboard'."""
    if live:
        _cmds.run_live_dashboard(refresh_seconds=refresh)
    else:
        _cmds.render_dashboard()

@cli.command()
def status():
    """
    Show Saleha system status
    """
    console.print(Panel.fit('[bold green]Saleha System Status[/]', border_style='green'))
    import urllib.request
    try:
        with urllib.request.urlopen('http://localhost:11434/api/version', timeout=2) as resp:
            ollama_alive = resp.status == 200
    except OSError:
        ollama_alive = False
    if ollama_alive:
        from saleha.core.smart_router import get_installed_ollama_models
        live_models = get_installed_ollama_models()
        if live_models:
            console.print(f'[green]✅ Ollama:[/] Connected ({len(live_models)} model(s) installed)')
            console.print(f"[green]   Models:[/] {', '.join(sorted(live_models)[:8])}")
        else:
            console.print('[green]✅ Ollama:[/] Connected (koi model installed nahi mila)')
    else:
        console.print('[red]❌ Ollama:[/] Not reachable at http://localhost:11434')
    router = _cmds.SmartRouter()
    stats = router.get_all_stats()
    total_uses = sum((s['uses'] for s in stats.values()))
    console.print(f'\n[cyan]📊 Total Tasks Processed:[/] {total_uses}')
    console.print(f'[cyan]🧠 Models Available:[/] {len(router.models)}')

@cli.command()
@click.option('--model', '-m', default='auto', help='Model to use')
def interactive(model):
    """
    Start interactive Saleha shell
    
    Example: saleha interactive
    """
    console.print(Panel.fit("[bold green]Saleha Interactive Shell[/]\nType 'exit' or 'quit' to leave\nType 'help' for commands\nType 'code: <task>' for coding tasks", border_style='green'))
    orchestrator = _cmds.SalehaOrchestrator(model=model)
    while True:
        try:
            user_input = console.input('\n[bold cyan]Saleha>[/] ').strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit']:
                console.print('[yellow]Goodbye![/]')
                break
            if user_input.lower() == 'help':
                console.print('\n[bold]Commands:[/]')
                console.print('  [cyan]code: <task>[/] - Coding task')
                console.print('  [cyan]<question>[/] - Normal chat')
                console.print('  [cyan]exit[/] - Exit shell')
                console.print('  [cyan]help[/] - Show this help\n')
                continue
            is_coding = user_input.lower().startswith('code:')
            if is_coding:
                task = user_input[5:].strip()
                result = orchestrator.execute_task(task)
                if result.success:
                    console.print(f'\n[green]✅ Success![/] ({result.attempts} attempts)')
                    console.print('\n[bold]Code:[/]')
                    syntax = Syntax(result.final_code, 'python', theme='monokai', line_numbers=True)
                    console.print(syntax)
                else:
                    console.print(f'\n[red]❌ Failed![/] ({result.attempts} attempts)')
            else:
                agent = _cmds.BaseAgent(role='Assistant', model=model)
                response = agent.think(user_input)
                if response.success:
                    console.print(f'\n[green]Saleha:[/] {response.content}')
                else:
                    console.print(f'\n[red]Error:[/] {response.error_message}')
        except KeyboardInterrupt:
            console.print('\n[yellow]Interrupted![/]')
            break
        except EOFError:
            break

@cli.command()
def tui():
    """Launch full-screen interactive Terminal TUI Canvas IDE."""
    _cmds.start_tui_canvas(console)

@cli.command()
def canvas():
    """Alias for 'saleha tui'."""
    _cmds.start_tui_canvas(console)

@cli.command(name='stream')
@click.argument('prompt')
@click.option('--model', '-m', default='auto', help='Model to stream from')
def stream_cmd(prompt, model):
    """Stream generated tokens in real-time with typewriter syntax highlighting."""
    from saleha.core.streaming_ui import streaming_ui
    streaming_ui.stream_to_terminal(model=model, prompt=prompt, title='Saleha Stream')

@cli.command(name='debug-repl')
def repl_cmd():
    """Start an interactive stateful Python AI REPL & live variable debugger.

    (Pehle ye 'repl' naam se registered tha, jisne 'saleha repl --profile'
    chat alias ko silently overwrite kar diya tha -- isliye rename kiya gaya.)
    """
    from saleha.core.debugger_repl import repl
    repl.interactive_loop()

@cli.command(name='hud')
@click.option('--once', is_flag=True, help='Render a single static snapshot without live loop')
@click.option('--rate', default=1.0, help='Refresh interval in seconds')
def hud_cmd(once, rate):
    """
    Live interactive Terminal Heads-Up Display (HUD) with real-time telemetry and hotkeys.
    
    Example: saleha hud
    """
    from saleha.cli.terminal_hud import terminal_hud
    if once:
        terminal_hud.render_once()
    else:
        terminal_hud.run_live(refresh_rate=rate)

@cli.command(name='dashboard')
def dashboard_cmd():
    """Launch terminal rich operations dashboard."""
    _cmds.render_dashboard()

@cli.command(name='ui')
def ui_cmd():
    """Launch terminal dashboard (alias)."""
    _cmds.render_dashboard()

@cli.command(name='watch-ai')
@click.argument('directory', default='.')
def watch_ai_cmd(directory):
    """
    Start Real-Time File Watcher with instant inline syntax & security hints.
    
    Example: saleha watch-ai .
    """
    from saleha.core.realtime_watcher import RealtimeWatcher
    watcher = RealtimeWatcher(root_dir=directory)
    console.print(f'[bold green]👀 Saleha Watch-AI is actively monitoring:[/] [cyan]{os.path.abspath(directory)}[/]')
    console.print('[dim]Edit any .py/.js/.ts file to see real-time suggestions. Press Ctrl+C to stop.[/]')

    def on_event(ev):
        if ev.suggestions:
            console.print(f'\n[bold yellow]⚡ File changed:[/] {ev.path}')
            for s in ev.suggestions:
                console.print(f'  {s.format()}')
    watcher.on_change(on_event)
    watcher.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        console.print('\n[yellow]Watch-AI stopped.[/]')

@cli.command(name='tui')
@click.option('--model', default='auto', help='Model to power the TUI session')
def tui_cmd(model: str):
    """
    Launch the full-screen interactive Terminal UI (Aider-style workspace).
    
    Example: saleha tui
    """
    from saleha.cli.tui_app import launch_tui
    launch_tui(model=model)

@cli.command('resume')
@click.argument('execution_id')
def resume_cli_cmd(execution_id: str):
    """Resume an interrupted swarm execution from its last saved checkpoint."""
    from saleha.core.swarm_pipeline_engine import swarm_engine
    from saleha.cli.swarm_visualizer import visualizer
    console.print(f'[bold cyan]🔄 Resuming Swarm Execution:[/] [yellow]{execution_id}[/]')
    try:
        res = swarm_engine.resume_swarm(execution_id)
        visualizer.render_execution_summary(res)
    except Exception as e:
        console.print(f'[bold red]❌ Failed to resume checkpoint:[/] {e}')

@cli.command('dev')
@click.option('--all', 'all_apps', is_flag=True, default=False, help='Launch backend server and frontend apps simultaneously')
@click.option('--port', default=8000, help='Backend server port')
def dev_cli_cmd(all_apps: bool, port: int):
    """Start local development server and client applications."""
    if all_apps:
        console.print('[bold cyan]🚀 Starting Saleha AI Multi-App Dev Ecosystem...[/bold cyan]')
        console.print('  • Backend Web Studio : http://127.0.0.1:8000')
        console.print('  • Next.js App Studio : http://localhost:3000')
        console.print('  • Astro Landing Page : http://localhost:4321')
        from saleha.server.web_server import run_web_studio
        _cmds.run_web_studio(port=port, open_browser=True)
    else:
        from saleha.server.web_server import run_web_studio
        _cmds.run_web_studio(port=port, open_browser=True)

@cli.command('chat')
def chat_cli_cmd():
    """Start interactive pair-programming chat playground."""
    from saleha.cli.chat_session import run_chat_repl
    run_chat_repl()

@cli.command('play')
def play_cli_cmd():
    """Alias for interactive chat playground."""
    from saleha.cli.chat_session import run_chat_repl
    run_chat_repl()

@cli.command('run-container')
@click.argument('code_or_file')
@click.option('--timeout', default=15.0, help='Hard timeout in seconds')
def run_container_cli_cmd(code_or_file: str, timeout: float):
    """Execute code inside isolated ephemeral Docker container with cgroup bounds."""
    from saleha.core.ephemeral_container_runner import container_runner
    console.print(f'\n[bold cyan]🐳 Ephemeral Container Sandbox — Launching Execution...[/bold cyan]\n')
    res = container_runner.run_code(code_or_file, timeout_sec=timeout)
    status_color = 'green' if res.success else 'red'
    console.print(f"[{status_color}]● Execution {('SUCCESS' if res.success else 'FAILED')} ({res.duration_ms}ms)[/{status_color}]")
    console.print(f'  • Engine    : {res.isolation_engine}')
    console.print(f'  • Exit Code : {res.exit_code}\n')
    if res.output:
        console.print(Panel(res.output, title='[bold green]Stdout Output[/]', border_style='green'))
    if res.error:
        console.print(Panel(res.error, title='[bold red]Stderr / Diagnostic Output[/]', border_style='red'))

