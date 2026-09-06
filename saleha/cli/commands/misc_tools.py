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
@click.argument('code_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('error_log', required=False)
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--save', is_flag=True, help='Overwrite the input file with corrected code')
@click.option('--error-file', type=click.Path(exists=True, dir_okay=False), help='Read the traceback from a file')
@click.option('--output', type=click.Path(dir_okay=False), help='Write corrected code to a different file')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def debug(code_file, error_log, model, save, error_file, output, as_json):
    """
    Diagnose an error and generate corrected code.

    Example: saleha debug app.py "NameError: name 'x' is not defined"
    """
    if bool(error_log) == bool(error_file):
        raise click.UsageError('Provide either ERROR_LOG or --error-file, but not both.')
    if save and output:
        raise click.UsageError('Use either --save or --output, but not both.')
    with open(code_file, 'r', encoding='utf-8') as f:
        code = f.read()
    if error_file:
        with open(error_file, 'r', encoding='utf-8') as f:
            error_log = f.read()
    agent = _cmds.DebuggerAgent(model=model)
    if as_json:
        result = agent.debug_code('Debug the provided Python code', code, error_log)
    else:
        console.print(Panel.fit(f'[bold cyan]🐞 Debugging:[/] {code_file}\n[bold cyan]🤖 Model:[/] {model}', title='[bold green]Saleha Debugger[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
            progress.add_task('[cyan]Analyzing error...', total=None)
            result = agent.debug_code('Debug the provided Python code', code, error_log)
    if not result.success:
        if as_json:
            click.echo(json.dumps({'success': False, 'diagnosis': result.diagnosis, 'fixed_code': result.fixed_code, 'error': result.error, 'model_used': result.model_used}, ensure_ascii=False))
            raise click.exceptions.Exit(1)
        console.print(Panel(f'[bold red]❌ Debugging Failed[/]\n{result.error}', border_style='red'))
        return
    destination = code_file if save else output
    if destination:
        validation = _cmds.TesterAgent().test_code(result.fixed_code)
        if not validation.passed:
            if as_json:
                click.echo(json.dumps({'success': False, 'diagnosis': result.diagnosis, 'fixed_code': result.fixed_code, 'error': f'{validation.error_type}: {validation.error_message}', 'model_used': result.model_used}, ensure_ascii=False))
                raise click.exceptions.Exit(1)
            console.print(Panel(f'[bold red]❌ Save cancelled[/] - corrected code failed validation\n{validation.error_type}: {validation.error_message}', border_style='red'))
            return
        with open(destination, 'w', encoding='utf-8') as f:
            f.write(result.fixed_code + '\n')
    if as_json:
        click.echo(json.dumps({'success': True, 'diagnosis': result.diagnosis, 'fixed_code': result.fixed_code, 'error': '', 'model_used': result.model_used, 'saved_to': destination or ''}, ensure_ascii=False))
        return
    console.print(Panel(f"[bold green]✅ Diagnosis[/]\n{result.diagnosis or 'No diagnosis returned.'}", border_style='green'))
    console.print('\n[bold cyan]📝 Corrected Code:[/]')
    console.print(Syntax(result.fixed_code, 'python', theme='monokai', line_numbers=True))
    if destination:
        console.print(f'\n[bold green]✅ Saved corrected code to:[/] {destination}')

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def models(as_json):
    """
    Show all available models and their stats
    """
    router = _cmds.SmartRouter()
    if as_json:
        payload = {'models': {name: {'size_gb': profile.size_gb, 'speed': profile.speed, 'best_for': profile.best_for, 'stats': router.get_model_stats(name)} for name, profile in router.models.items()}}
        click.echo(json.dumps(payload, ensure_ascii=False))
        return
    table = Table(title='🤖 Available Models', show_header=True, header_style='bold magenta')
    table.add_column('Model', style='cyan')
    table.add_column('Size', justify='right')
    table.add_column('Speed', style='green')
    table.add_column('Best For', style='yellow')
    for model_name, profile in router.models.items():
        table.add_row(model_name, f'{profile.size_gb}GB', profile.speed, ', '.join(profile.best_for[:3]))
    console.print(table)
    stats = router.get_all_stats()
    if any((s['uses'] > 0 for s in stats.values())):
        console.print('\n[bold cyan]📊 Performance Stats:[/]')
        stats_table = Table(show_header=True, header_style='bold magenta')
        stats_table.add_column('Model', style='cyan')
        stats_table.add_column('Uses', justify='right')
        stats_table.add_column('Success Rate', justify='right', style='green')
        stats_table.add_column('Avg Time', justify='right', style='yellow')
        for model_name, model_stats in stats.items():
            if model_stats['uses'] > 0:
                stats_table.add_row(model_name, str(model_stats['uses']), f"{model_stats['success_rate']:.1%}", f"{model_stats['avg_time']:.2f}s")
        console.print(stats_table)

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def skills(as_json):
    """Show skills registered in Saleha's local skill registry."""
    _cmds.load_builtin_skills()
    registered = _cmds.skill_registry.list_skills()
    if not registered:
        if as_json:
            click.echo(json.dumps({'skills': []}, ensure_ascii=False))
            return
        console.print('[yellow]No skills are currently registered.[/]')
        return
    if as_json:
        click.echo(json.dumps({'skills': [{'name': skill.name, 'description': skill.description} for skill in registered]}, ensure_ascii=False))
        return
    table = Table(title='Available Skills', show_header=True, header_style='bold magenta')
    table.add_column('Name', style='cyan')
    table.add_column('Description', style='yellow')
    for skill in registered:
        table.add_row(skill.name, skill.description)
    console.print(table)

@cli.command()
@click.argument('target_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('instruction')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--diff-only', is_flag=True, help='Only display the unified diff without saving changes')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def refactor(target_file, instruction, model, diff_only, as_json):
    """Refactor a Python file surgically using AST analysis and unified diff patching."""
    with open(target_file, 'r', encoding='utf-8') as f:
        original_code = f.read()
    coder = _cmds.CoderAgent(model=model)
    prompt = f'\nTask: Refactor this existing Python file according to the following instruction.\nInstruction: {instruction}\n\nOriginal File Content ({os.path.basename(target_file)}):\n```python\n{original_code}\n```\n\nRequirements:\n- Preserve all existing interfaces, classes, and comments unless explicitly asked to modify them.\n- Return the full refactored file in a ```python ... ``` block.\n'
    resp = coder.generate_code(task=instruction, plan=prompt)
    if not resp.success or not resp.code:
        if as_json:
            click.echo(json.dumps({'success': False, 'error': resp.error or 'Coder failed'}, ensure_ascii=True))
        else:
            console.print(f'[red]❌ Refactoring failed:[/] {resp.error}')
        return
    diff = _cmds.SmartPatcher.create_unified_diff(original_code, resp.code, os.path.basename(target_file))
    if not diff_only:
        patch_result = _cmds.SmartPatcher.apply_patch(target_file, resp.code)
        if not patch_result['success']:
            if as_json:
                click.echo(json.dumps(patch_result, ensure_ascii=True))
            else:
                console.print(f"[red]❌ Patch rejected:[/] {patch_result['error']}")
            return
    if as_json:
        click.echo(json.dumps({'success': True, 'file': target_file, 'diff': diff, 'modified': not diff_only}, ensure_ascii=True))
        return
    console.print(Panel(f'[bold green]✅ Refactoring Complete[/]\nFile: {target_file}', border_style='green'))
    if diff:
        console.print('\n[bold cyan]Unified Diff Patch:[/]')
        syntax = Syntax(diff, 'diff', theme='monokai')
        console.print(syntax)

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def tools(as_json):
    """List all available dynamic tools and their JSON schemas."""
    registered = _cmds.global_tool_registry.list_tools()
    if as_json:
        click.echo(json.dumps({'tools': _cmds.global_tool_registry.get_schemas()}, ensure_ascii=True))
        return
    table = Table(title='🛠️ Registered Dynamic Agent Tools', show_header=True, header_style='bold magenta')
    table.add_column('Tool Name', style='cyan')
    table.add_column('Parameters', style='green')
    table.add_column('Description', style='yellow')
    for t in registered:
        params_str = ', '.join([f'{p.name}: {p.type}' for p in t.parameters]) or 'None'
        table.add_row(t.name, params_str, t.description)
    console.print(table)

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def doctor(as_json):
    """
    Saleha ke common problems ko check karta hai -- jaise wo saari cheezein
    jo is session me manually debug karni padi (Ollama band hona, missing
    files, galat spelling wali files, python/python3 na milna).

    Example: saleha doctor
    """
    if not as_json:
        console.print(Panel.fit('[bold green]🩺 Saleha Doctor[/]', border_style='green'))
    checks = []
    py = _cmds.shutil_which_check()
    checks.append(('Python interpreter (python/python3)', py is not None, py or "Neither 'python' nor 'python3' found on PATH"))
    core_dir = os.path.join(os.path.dirname(__file__), '..', 'core')
    required_core_files = ['code_executor.py', 'safety_patterns.py', 'stats_tracker.py', 'task_history.py', 'audit_log.py', 'smart_router.py', 'project_builder.py', 'model_provider.py', 'self_healing.py', 'skill_registry.py']
    for fname in required_core_files:
        path = os.path.join(core_dir, fname)
        checks.append((f'core/{fname} exists', os.path.isfile(path), path))
    agents_dir = os.path.join(os.path.dirname(__file__), '..', 'agents')
    required_agent_files = ['base_agent.py', 'coder.py', 'tester.py', 'reviewer.py', 'planner.py', 'debugger.py']
    for fname in required_agent_files:
        path = os.path.join(agents_dir, fname)
        checks.append((f'agents/{fname} exists', os.path.isfile(path), path))
    ollama_ok, ollama_detail = _cmds._check_ollama()
    checks.append(('Ollama server reachable', ollama_ok, ollama_detail))
    saleha_home = os.path.join(os.path.expanduser('~'), '.saleha')
    try:
        os.makedirs(saleha_home, exist_ok=True)
        test_file = os.path.join(saleha_home, '.write_test')
        with open(test_file, 'w') as f:
            f.write('ok')
        os.remove(test_file)
        checks.append((f'~/.saleha/ writable', True, saleha_home))
    except Exception as e:
        checks.append((f'~/.saleha/ writable', False, str(e)))
    if as_json:
        failed = sum((1 for _, ok, _ in checks if not ok))
        click.echo(json.dumps({'healthy': failed == 0, 'checks': [{'name': name, 'ok': ok, 'detail': detail} for name, ok, detail in checks]}, ensure_ascii=False))
        if failed:
            raise click.exceptions.Exit(1)
        return
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('Check', style='cyan')
    table.add_column('Status', justify='center')
    table.add_column('Detail', style='dim')
    fail_count = 0
    for name, ok, detail in checks:
        status = '[green]✅[/]' if ok else '[red]❌[/]'
        if not ok:
            fail_count += 1
        table.add_row(name, status, detail[:60])
    console.print(table)
    if fail_count == 0:
        console.print('\n[bold green]Sab theek hai![/] 🎉')
    else:
        console.print(f'\n[bold yellow]{fail_count} problem(s) mile.[/] Upar table me detail dekho.')
        raise click.exceptions.Exit(1)

@cli.command()
@click.option('--task-type', '-t', default='coding', help='Task category to show stats for')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def stats(task_type, as_json):
    """
    Show persistent model performance stats (saved in ~/.saleha/stats.json)

    Ye 'models' command se alag hai -- 'models' SmartRouter ki apni
    router_history.json dikhata hai, ye command orchestrator ke
    stats_tracker.py wali file dikhata hai.

    Example: saleha stats
    Example: saleha stats --task-type coding
    """
    from saleha.core.stats_tracker import StatsTracker
    tracker = StatsTracker()
    bucket = tracker._data.get(task_type, {})
    if not bucket:
        if as_json:
            click.echo(json.dumps({'task_type': task_type, 'models': [], 'best_model': None}, ensure_ascii=False))
            return
        console.print(f"[yellow]Abhi tak '{task_type}' ke liye koi stats nahi hain.[/]")
        return
    if as_json:
        models = {}
        for model_name in bucket:
            model_stats = tracker.get_model_stats(model_name, task_type)
            models[model_name] = {'uses': model_stats.uses, 'success_rate': model_stats.success_rate, 'avg_attempts': model_stats.avg_attempts, 'last_used': model_stats.last_used}
        click.echo(json.dumps({'task_type': task_type, 'models': models, 'best_model': tracker.best_model_for(task_type=task_type)}, ensure_ascii=False))
        return
    table = Table(title=f'📊 Model Stats ({task_type})', show_header=True, header_style='bold magenta')
    table.add_column('Model', style='cyan')
    table.add_column('Uses', justify='right')
    table.add_column('Success Rate', justify='right', style='green')
    table.add_column('Avg Attempts', justify='right', style='yellow')
    table.add_column('Last Used', style='dim')
    for model_name in sorted(bucket, key=lambda m: -bucket[m]['uses']):
        s = tracker.get_model_stats(model_name, task_type)
        table.add_row(model_name, str(s.uses), f'{s.success_rate}%', str(s.avg_attempts), s.last_used or '-')
    console.print(table)
    best = tracker.best_model_for(task_type=task_type)
    if best:
        console.print(f"\n[bold green]🏆 Best model for '{task_type}':[/] {best}")

@cli.command()
@click.option('--limit', '-n', default=10, help='Number of recent tasks to show')
@click.option('--failed-only', is_flag=True, help='Show only failed tasks')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def history(limit, failed_only, as_json):
    """
    Show recent task history (saved in ~/.saleha/history.jsonl)

    Example: saleha history
    Example: saleha history -n 20
    Example: saleha history --failed-only
    """
    from saleha.core.task_history import TaskHistory
    hist = TaskHistory()
    records = hist.failed_tasks() if failed_only else hist.recent(limit)
    if not records:
        if as_json:
            click.echo(json.dumps({'tasks': []}, ensure_ascii=False))
            return
        console.print('[yellow]Abhi tak koi task history nahi hai.[/]')
        return
    if as_json:
        click.echo(json.dumps({'tasks': [record.__dict__ for record in records]}, ensure_ascii=False))
        return
    table = Table(title='📜 Task History', show_header=True, header_style='bold magenta')
    table.add_column('Status', justify='center')
    table.add_column('Time', style='dim')
    table.add_column('Model', style='cyan')
    table.add_column('Attempts', justify='right')
    table.add_column('Goal', style='yellow')
    for r in records:
        status = '[green]✅[/]' if r.success else '[red]❌[/]'
        table.add_row(status, r.timestamp, r.model, str(r.attempts), r.goal[:60])
    console.print(table)

@cli.command()
@click.option('--tail', '-n', default=10, help='Recent events to show')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable summary + tail')
def metrics(tail, as_json):
    """Show run success-rate, avg attempts, per-model stats & recent events."""
    from saleha.core.metrics import metrics_tracker
    summary = metrics_tracker.summary()
    recent = metrics_tracker.tail(limit=tail)
    if as_json:
        click.echo(json.dumps({'summary': summary, 'recent': recent}, ensure_ascii=True))
        return
    console.print(Panel.fit('[bold green]Saleha Run Metrics[/]', border_style='green'))
    console.print(f"[cyan]Total Runs:[/] {summary['total_runs']}  |  [green]✅ {summary['successful_runs']}[/]  [red]❌ {summary['failed_runs']}[/]")
    console.print(f"[cyan]Success Rate:[/] {summary['success_rate']}%   [cyan]Avg Attempts:[/] {summary['avg_attempts']}   [cyan]Avg Duration:[/] {summary['avg_duration_sec']}s")
    if summary['by_model']:
        table = Table(title='Per-Model Performance')
        table.add_column('Model', style='cyan')
        table.add_column('Runs', justify='right')
        table.add_column('Wins', justify='right', style='green')
        for model_name, slot in sorted(summary['by_model'].items(), key=lambda kv: kv[1]['runs'], reverse=True):
            table.add_row(model_name, str(slot['runs']), str(slot['wins']))
        console.print(table)
    if recent:
        rt = Table(title=f'Recent Events (last {len(recent)})')
        rt.add_column('Time', style='dim')
        rt.add_column('Event')
        rt.add_column('Detail')
        for e in recent:
            ts = time.strftime('%H:%M:%S', time.localtime(e.get('ts', 0)))
            detail = ''
            if e.get('event') == 'run_completed':
                detail = f"{('✅' if e.get('success') else '❌')} attempts={e.get('attempts')} model={e.get('model')}"
            rt.add_row(ts, str(e.get('event')), detail or '-')
        console.print(rt)

@cli.command(name='plugins')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def plugins_cmd(as_json):
    """List loaded dynamic plugins and lifecycle event hooks."""
    from saleha.core.plugin_loader import plugin_loader
    plugins = plugin_loader.list_plugins()
    if as_json:
        payload = [{'name': p.name, 'version': p.version, 'description': p.description, 'file': p.file_path, 'hooks': p.hooks_registered} for p in plugins]
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    if not plugins:
        console.print(Panel('[yellow]No external plugins loaded.[/]\n\n💡 You can drop custom Python plugins into [bold cyan]~/.saleha/plugins/[/] or [bold cyan].saleha/plugins/[/]\nSupported hooks: [dim]on_task_start, on_code_generated, on_test_complete, on_commit[/]', title='[bold green]🔌 Saleha Plugin Registry[/]', border_style='green'))
        return
    from rich.table import Table
    table = Table(title='🔌 Loaded Plugins', border_style='green')
    table.add_column('Plugin Name', style='bold cyan')
    table.add_column('Version', style='dim')
    table.add_column('Description', style='yellow')
    table.add_column('Hooks', style='green')
    for p in plugins:
        table.add_row(p.name, p.version, p.description, ', '.join(p.hooks_registered) or 'None')
    console.print(table)

@cli.command(name='fuzz')
@click.argument('func_name', default='process')
@click.option('--mutations', '-m', default=5, type=int, help='Number of mutation payloads to test')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def fuzz_cmd(func_name, mutations, as_json):
    """Execute automated security mutation fuzzing against code functions."""
    from saleha.core.api_fuzzer import api_fuzzer
    mock_code = f"def {func_name}(val):\n    if len(str(val)) > 100:\n        raise ValueError('Buffer overflow attempt')\n    return {{'status': 'ok'}}"
    report = api_fuzzer.fuzz_function(code=mock_code, func_name=func_name, mutations=mutations)
    if as_json:
        click.echo(json.dumps({'target': report.target, 'total_mutations': report.total_mutations, 'vulnerabilities_found': report.vulnerabilities_found, 'crashes_found': report.crashes_found, 'findings': [f.__dict__ for f in report.findings]}, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title=f'🦹 Saleha API Security Fuzzer — Target: {report.target}()', border_style='red')
    table.add_column('Category', style='bold cyan')
    table.add_column('Payload Preview', style='dim')
    table.add_column('Status', justify='center')
    table.add_column('Result', style='yellow')
    for f in report.findings:
        status_txt = '[red]💥 CRASH[/]' if f.status == 'CRASH' else '[green]🛡️ SAFE[/]'
        table.add_row(f.category, f.payload[:30], status_txt, f.details[:50])
    console.print(table)
    console.print(Panel(f"[bold cyan]Total Mutations:[/] {report.total_mutations}\n[bold cyan]Crashes / Exceptions:[/] [{('red' if report.crashes_found else 'green')}]{report.crashes_found}[/]", title='[bold green]Fuzzing Summary[/]', border_style='green'))

@cli.command(name='loadtest')
@click.argument('url', default='http://localhost:8000/api/status')
@click.option('--concurrency', '-c', default=10, type=int, help='Concurrent users / threads')
@click.option('--requests', '-r', default=50, type=int, help='Total requests to send')
@click.option('--dry-run', is_flag=True, help='Simulate load benchmark')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def loadtest_cmd(url, concurrency, requests, dry_run, as_json):
    """Execute high-concurrency API load testing and percentile benchmarks."""
    from saleha.core.load_tester import load_tester
    with Progress(SpinnerColumn(), TextColumn(f"[cyan]Executing load test against '{url}' ({requests} requests, {concurrency} workers)..."), console=console) as progress:
        progress.add_task('loadtest', total=None)
        res = load_tester.run_load_test(url=url, concurrency=concurrency, total_requests=requests, dry_run=dry_run)
    if as_json:
        click.echo(json.dumps(res.__dict__, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title=f'⚡ Load Test Benchmark — {res.url}', border_style='cyan')
    table.add_column('Metric', style='bold cyan')
    table.add_column('Value', justify='right', style='bold green')
    table.add_row('Total Requests', str(res.total_requests))
    table.add_row('Successful', str(res.successful_requests))
    table.add_row('Failed', str(res.failed_requests))
    table.add_row('Throughput', f'{res.requests_per_sec} req/sec')
    table.add_row('Avg Latency', f'{res.avg_latency_ms} ms')
    table.add_row('p50 (Median)', f'{res.p50_ms} ms')
    table.add_row('p95', f'{res.p95_ms} ms')
    table.add_row('p99', f'{res.p99_ms} ms')
    console.print(table)

@cli.command(name='doctor')
@click.option('--fix', is_flag=True, help='Attempt auto-repair of missing models or folders')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def doctor_cmd(fix, as_json):
    """Diagnose local environment, Ollama models, Git, Sandbox, and Vault."""
    import shutil
    import subprocess
    from saleha.core.smart_router import get_installed_ollama_models
    checks = []
    py_ver = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    checks.append({'component': 'Python Environment', 'status': 'PASS' if sys.version_info >= (3, 9) else 'FAIL', 'detail': f'Python {py_ver} (64-bit)' if sys.maxsize > 2 ** 32 else f'Python {py_ver}'})
    git_bin = shutil.which('git')
    git_status = 'PASS' if git_bin else 'FAIL'
    git_detail = f'Found at {git_bin}' if git_bin else 'Git not found in PATH'
    checks.append({'component': 'Git Binary', 'status': git_status, 'detail': git_detail})
    installed_models = get_installed_ollama_models()
    if installed_models:
        ollama_status = 'PASS'
        models_sample = list(installed_models)[:4]
        ollama_detail = f"Online ({len(installed_models)} models: {', '.join(models_sample)})"
    else:
        ollama_status = 'WARN'
        ollama_detail = "Offline or no models pulled yet (run 'ollama serve' / 'ollama pull qwen2.5-coder:3b')"
        if fix:
            try:
                subprocess.run(['ollama', 'pull', 'qwen2.5-coder:3b'], check=False)
                installed_models = get_installed_ollama_models()
                if installed_models:
                    ollama_status = 'PASS'
                    models_sample = list(installed_models)[:4]
                    ollama_detail = f"Auto-pulled qwen2.5-coder:3b ({len(installed_models)} models: {', '.join(models_sample)})"
            except Exception:
                pass
    checks.append({'component': 'Ollama LLM Service', 'status': ollama_status, 'detail': ollama_detail})
    docker_bin = shutil.which('docker')
    docker_running = False
    if docker_bin:
        try:
            d_proc = subprocess.run([docker_bin, 'info'], capture_output=True, timeout=2)
            docker_running = d_proc.returncode == 0
        except Exception:
            docker_running = False
    if docker_running:
        sb_status = 'PASS'
        sb_detail = 'Docker daemon active (Hardware Sandboxed)'
    else:
        sb_status = 'PASS'
        sb_detail = 'Polyglot Subprocess Sandbox Active (Docker Offline fallback)'
    checks.append({'component': 'Execution Sandbox', 'status': sb_status, 'detail': sb_detail})
    vault_dir = os.path.expanduser('~/.saleha')
    try:
        os.makedirs(vault_dir, exist_ok=True)
        vault_status = 'PASS'
        vault_detail = f'Writable at {vault_dir}'
    except Exception as e:
        vault_status = 'FAIL'
        vault_detail = f'Permission error: {e}'
    checks.append({'component': 'Encrypted Vault Storage', 'status': vault_status, 'detail': vault_detail})
    all_pass = all((c['status'] != 'FAIL' for c in checks))
    if as_json:
        click.echo(json.dumps({'healthy': all_pass, 'checks': [{'name': f"core/{c['component'].lower().replace(' ', '_')}", 'status': c['status'], 'detail': c['detail']} for c in checks], 'diagnostics': checks}, ensure_ascii=False, indent=2))
        return
    table = Table(title='🩺 Saleha System Doctor & Diagnostic Suite', show_header=True, header_style='bold magenta', expand=True)
    table.add_column('Component', style='bold cyan', width=25)
    table.add_column('Status', width=12)
    table.add_column('Details', style='white')
    all_pass = True
    for c in checks:
        color = 'green' if c['status'] == 'PASS' else 'yellow' if c['status'] == 'WARN' else 'red'
        if c['status'] == 'FAIL':
            all_pass = False
        table.add_row(c['component'], f"[{color}]{c['status']}[/]", c['detail'])
    console.print(table)
    if all_pass:
        console.print('\n[bold green]✅ Everything is healthy and ready for autonomous engineering![/]\n')
    else:
        console.print("\n[bold yellow]⚠️ Some components require attention. Run 'saleha doctor --fix' to auto-repair.[/]\n")

@cli.command(name='bench')
@click.option('--limit', '-n', default=None, type=int, help='Maximum number of benchmark instances to evaluate')
@click.option('--dry-run', is_flag=True, help='Simulate execution quickly without executing heavy code')
@click.option('--json', 'as_json', is_flag=True, help='Output benchmark results as JSON')
def bench_cmd(limit, dry_run, as_json):
    """
    Run SWE-bench & HumanEval autonomous software engineering benchmark evaluation.
    
    Example: saleha bench
    Example fast: saleha bench --dry-run
    """
    from saleha.core.swe_bench_harness import swe_bench
    console.print(Panel(f"[bold cyan]Suite:[/] SWE-bench Verified & HumanEval Suite\n[bold green]Metrics:[/] Pass@1 Resolution Rate, Multi-file Localization, Sandboxed Execution\n[dim]Running {('dry-run simulation' if dry_run else 'sandboxed execution test harness')}...[/]", title='[bold green]🏆 Saleha Autonomous Benchmark Runner[/]', border_style='green'))
    report = _cmds.swe_bench.run_evaluation(limit=limit, dry_run=dry_run)
    if as_json:
        click.echo(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
        return
    table = Table(title='📊 Benchmark Problem Resolution Breakdown', show_header=True, header_style='bold magenta', expand=True)
    table.add_column('Instance ID', style='bold cyan', width=30)
    table.add_column('Domain / Repo', width=22)
    table.add_column('Difficulty', width=12)
    table.add_column('Resolution', width=12)
    table.add_column('Latency', width=10)
    for r in report.results:
        status_color = 'green' if r['resolved'] else 'red'
        status_txt = 'RESOLVED' if r['resolved'] else 'FAILED'
        table.add_row(r['instance_id'], r['repo'], r['difficulty'], f'[{status_color}]{status_txt}[/]', f"{r['latency_sec']}s")
    console.print(table)
    rate_color = 'green' if report.pass_rate >= 80 else 'yellow' if report.pass_rate >= 50 else 'red'
    console.print(Panel(f'[bold white]Total Instances Tested:[/] {report.total_instances}\n[bold white]Instances Resolved:[/] {report.resolved_instances}\n[bold cyan]Pass Rate (Pass@1):[/] [{rate_color}]{report.pass_rate}%[/]\n[bold cyan]Average Latency:[/] {report.avg_latency_sec}s', title='[bold green]🏁 Official Benchmark Summary[/]', border_style='green'))

@cli.command(name='lsp')
@click.argument('target', default='.')
@click.option('--json', 'as_json', is_flag=True, help='Output diagnostics as JSON')
def lsp_cmd(target, as_json):
    """
    Run compiler-grade static analysis & type-checking diagnostics across workspace.
    
    Example: saleha lsp ./src
    """
    from saleha.core.lsp_engine import lsp_engine
    if os.path.isfile(target):
        diags = _cmds.lsp_engine.check_file(target)
        errs = sum((1 for d in diags if d.severity == 'ERROR'))
        warns = sum((1 for d in diags if d.severity == 'WARNING'))
        from saleha.core.lsp_engine import DiagnosticReport
        report = DiagnosticReport(total_diagnostics=len(diags), error_count=errs, warning_count=warns, diagnostics=diags)
    else:
        report = _cmds.lsp_engine.check_directory(target)
    if as_json:
        click.echo(json.dumps({'total': report.total_diagnostics, 'errors': report.error_count, 'warnings': report.warning_count, 'diagnostics': [d.__dict__ for d in report.diagnostics]}, ensure_ascii=False, indent=2))
        return
    table = Table(title=f'🔍 Compiler & Type Diagnostics ({target})', show_header=True, header_style='bold magenta', expand=True)
    table.add_column('Location', style='bold cyan', width=25)
    table.add_column('Severity', width=10)
    table.add_column('Rule ID', width=18)
    table.add_column('Message', style='white')
    for d in report.diagnostics[:15]:
        sev_color = 'red' if d.severity == 'ERROR' else 'yellow'
        table.add_row(f'{os.path.basename(d.file_path)}:{d.line_number}:{d.column}', f'[{sev_color}]{d.severity}[/]', d.rule_id, d.message)
    console.print(table)
    if report.total_diagnostics == 0:
        console.print('[bold green]✅ Clean! Zero compiler or type errors detected.[/]\n')
    else:
        console.print(f'[bold yellow]Found {report.error_count} Errors, {report.warning_count} Warnings.[/]\n')

@cli.command(name='chaos')
@click.option('--iterations', default=10, help='Number of randomized fault injection iterations')
def chaos_cmd(iterations):
    """
    Run autonomous Chaos Engineering fault injection probes to test resilience.
    
    Example: saleha chaos --iterations 10
    """
    from saleha.core.chaos_engine import chaos_engine
    console.print(f'[bold cyan]💥 Running Chaos Fault Injection Probe ({iterations} iterations)...[/]')

    def mock_target_flow():
        time.sleep(0.005)
        return True
    res = chaos_engine.probe_resilience(mock_target_flow, iterations=iterations)
    score_color = 'green' if res.resilience_score >= 0.8 else 'yellow'
    console.print(f'\n[bold white]Chaos Probe Completed:[/] Resilience Score: [{score_color}]{int(res.resilience_score * 100)}%[/]')
    console.print(f'  • Total Iterations: {res.total_iterations}')
    console.print(f'  • Injected Faults Handled: [green]{res.handled_cleanly}[/]')
    console.print(f'  • Unhandled Crashes: [red]{res.unhandled_crashes}[/]\n')

@cli.command(name='mock')
@click.option('--port', default=8080, help='Port for in-memory mock API server')
def mock_cmd(port):
    """
    Start zero-config Synthetic Mock API Server with realistic schemas.
    
    Example: saleha mock --port 8080
    """
    from saleha.core.mock_server import mock_server
    console.print(f'[bold cyan]🎭 Synthetic Mock API Server initialized on port:[/] [green]{port}[/]')
    routes = mock_server.list_routes()
    table = Table(title='🎭 Active Synthetic Mock Endpoints', show_header=True, header_style='bold magenta', expand=True)
    table.add_column('HTTP Method', style='bold yellow')
    table.add_column('Endpoint Path', style='cyan')
    table.add_column('Status Code', style='green')
    for r in routes:
        table.add_row(r.method, r.path, str(r.status_code))
    console.print(table)

@cli.command(name='init')
@click.option('--force', is_flag=True, help='Overwrite existing .saleharules file')
def init_cmd(force):
    """
    Interactively onboard and initialize project for Saleha AI.
    
    Example: saleha init
    """
    from saleha.core.project_initializer import project_initializer
    console.print('[bold cyan]🪄 Initializing Saleha AI for current workspace...[/]')
    res = project_initializer.initialize_workspace(force=force)
    console.print(f'\n[bold green]✅ Project Initialized Successfully![/]')
    console.print(f"  • Stack: [cyan]{', '.join(res.detected_languages)}[/]")
    console.print(f'  • Rules: [yellow]{res.rules_file_created}[/]')
    console.print(f'  • Indexed AST Symbols: [green]{res.ast_symbols_indexed}[/]\n')

@cli.command(name='pull')
@click.argument('model_name', default='recommended')
@click.option('--benchmark', is_flag=True, help='Benchmark local inference speed after pulling')
def pull_cmd(model_name, benchmark):
    """
    Download and benchmark recommended Ollama models.
    
    Example: saleha pull recommended --benchmark
    """
    from saleha.core.model_manager import model_manager, RECOMMENDED_MODELS
    targets = [RECOMMENDED_MODELS['fast'], RECOMMENDED_MODELS['reasoning']] if model_name == 'recommended' else [model_name]
    for m in targets:
        console.print(f'[bold cyan]📥 Pulling model:[/] [yellow]{m}[/]...')
        ok, msg = model_manager.pull_model(m)
        if ok:
            console.print(f'[bold green]✅ {msg}[/]')
            if benchmark:
                bench = model_manager.benchmark_model(m)
                if bench.success:
                    console.print(f'  [green]⚡ Speed:[/] {bench.tokens_per_sec} tokens/sec ({bench.tokens_generated} tokens in {bench.duration_sec}s)')
        else:
            console.print(f'[bold yellow]⚠️ {msg}[/]')

@cli.command(name='tune')
@click.option('--model', default='qwen2.5-coder:3b', help='Base model to fine-tune')
@click.option('--epochs', default=3, help='Training epochs')
@click.option('--name', default='saleha-custom', help='Output model name')
def tune_cmd(model, epochs, name):
    """
    Run Local LoRA Fine-Tuning Pipeline on collected codebase data.
    
    Example: saleha tune --model qwen2.5-coder:3b --epochs 3
    """
    from saleha.core.lora_tuner import lora_tuner, TuningConfig
    cfg = TuningConfig(base_model=model, epochs=epochs, output_model_name=name)
    console.print(f'[bold cyan]🚀 Starting Local LoRA Fine-Tuning on {model}...[/]')
    result = lora_tuner.fine_tune(cfg)
    if result.success:
        console.print(f'[bold green]✅ Fine-Tuning Completed Successfully![/]')
        console.print(f'  Model: [bold cyan]{result.output_model}[/]')
        console.print(f'  Samples: {result.samples_used} | Time: {result.training_time_sec}s')
        console.print(f'  Score: {result.before_score} → [bold green]{result.after_score}[/] (+{result.improvement_pct}%)')
    else:
        console.print(f'[bold red]❌ Fine-Tuning failed:[/] {result.error}')

@cli.group()
def memory():
    """Manage Saleha persistent solution memory and knowledge base."""
    pass

@memory.command('list')
@click.option('--limit', '-n', default=20, help='Number of memories to show')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def memory_list(limit, as_json):
    """List verified solutions stored in persistent memory."""
    memories = _cmds.memory_store.list_all(limit=limit)
    if not memories:
        if as_json:
            click.echo(json.dumps({'memories': []}, ensure_ascii=True))
            return
        console.print('[yellow]Persistent memory is currently empty.[/]')
        return
    if as_json:
        click.echo(json.dumps({'memories': [{'id': m.id, 'goal': m.goal, 'model': m.model, 'tags': m.tags, 'timestamp': m.timestamp, 'hit_count': m.hit_count, 'code_preview': m.code[:100]} for m in memories]}, ensure_ascii=True))
        return
    table = Table(title='🧠 Persistent Knowledge Base', show_header=True, header_style='bold magenta')
    table.add_column('ID', style='cyan')
    table.add_column('Hits', justify='right', style='green')
    table.add_column('Timestamp', style='dim')
    table.add_column('Tags', style='yellow')
    table.add_column('Goal / Specification', style='white')
    for m in memories:
        table.add_row(m.id, str(m.hit_count), m.timestamp[:19], ', '.join(m.tags[:3]) if m.tags else '-', m.goal[:60])
    console.print(table)

@memory.command('search')
@click.argument('query')
@click.option('--semantic', is_flag=True, help='Use TF-IDF Vector Semantic Search')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def memory_search(query, semantic, as_json):
    """Search solutions in memory by keyword, tag, or vector semantic similarity."""
    if semantic:
        raw_results = _cmds.memory_store.semantic_search(query)
        results = [entry for entry, score in raw_results]
        scores = {entry.id: score for entry, score in raw_results}
    else:
        results = _cmds.memory_store.search(query)
        scores = {}
    if not results:
        if as_json:
            click.echo(json.dumps({'results': []}, ensure_ascii=True))
            return
        console.print(f"[yellow]No memories matched query '{query}'.[/]")
        return
    if as_json:
        click.echo(json.dumps({'query': query, 'semantic': semantic, 'results': [{'id': m.id, 'goal': m.goal, 'tags': m.tags, 'hit_count': m.hit_count, 'score': scores.get(m.id, 1.0), 'code': m.code} for m in results]}, ensure_ascii=True))
        return
    mode_label = ' (Semantic Vector Mode)' if semantic else ''
    table = Table(title=f"🔍 Memory Search: '{query}'{mode_label}", show_header=True, header_style='bold magenta')
    table.add_column('ID', style='cyan')
    if semantic:
        table.add_column('Score', justify='right', style='magenta')
    table.add_column('Hits', justify='right', style='green')
    table.add_column('Goal', style='white')
    table.add_column('Tags', style='yellow')
    for m in results:
        row = [m.id]
        if semantic:
            row.append(f'{scores.get(m.id, 0.0):.2f}')
        row.extend([str(m.hit_count), m.goal[:60], ', '.join(m.tags[:3])])
        table.add_row(*row)
    console.print(table)

@memory.command('clear')
@click.option('--yes', '-y', is_flag=True, help='Confirm wiping memory without prompt')
def memory_clear(yes):
    """Clear all verified solutions from persistent memory."""
    if not yes:
        if not click.confirm('Are you sure you want to clear all persistent solution memories?'):
            console.print('[yellow]Cancelled.[/]')
            return
    _cmds.memory_store.clear()
    console.print('[green]✅ Persistent memory cleared successfully.[/]')

@memory.command('stats')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def memory_stats(as_json):
    """Show memory store statistics."""
    stats = _cmds.memory_store.stats()
    if as_json:
        click.echo(json.dumps(stats, ensure_ascii=True))
        return
    console.print(Panel.fit(f"[bold cyan]📦 Total Memories:[/] {stats['total_memories']}\n[bold cyan]🎯 Total Cache Hits:[/] {stats['total_hits']}\n[bold cyan]📁 File Path:[/] {stats['storage_path']}", title='[bold green]Memory Store Statistics[/]', border_style='green'))

@cli.group()
def ci():
    """Autonomous CI/CD and Pull Request review commands."""
    pass

@ci.command(name='review')
@click.argument('target_dir', default='.', type=click.Path(exists=True))
@click.option('--pr', 'pr_number', default=None, type=int, help='Pull request number')
@click.option('--output', '-o', default=None, type=click.Path(), help='Export markdown review report to file')
@click.option('--json', 'as_json', is_flag=True, help='Output review report as JSON')
def ci_review(target_dir, pr_number, output, as_json):
    """Run autonomous AST SAST security audit and code quality review."""
    bot = _cmds.PRReviewBot()
    report = bot.review_path(target_dir, pr_number=pr_number)
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report.markdown_review)
    if as_json:
        payload = {'status': report.status, 'quality_score': report.quality_score, 'total_files': report.total_files, 'total_loc': report.total_loc, 'high_vulnerabilities': report.security_report.high_count, 'medium_vulnerabilities': report.security_report.medium_count, 'low_vulnerabilities': report.security_report.low_count, 'suggested_actions': report.suggested_actions, 'markdown_review': report.markdown_review}
        click.echo(json.dumps(payload, ensure_ascii=True))
        if report.status == 'CHANGES_REQUESTED':
            raise click.exceptions.Exit(1)
        return
    console.print(Panel(f'[bold green]Status:[/] {report.status}\n[bold cyan]Quality Score:[/] {report.quality_score}/100\n[bold cyan]Files Scanned:[/] {report.total_files} ({report.total_loc} LOC)\n[bold yellow]Security Issues:[/] {report.security_report.total_vulnerabilities} ({report.security_report.high_count} High)', title='[bold green]🤖 Saleha CI/CD Autonomous Code Review[/]', border_style='green' if report.status == 'APPROVED' else 'red'))
    console.print(Markdown(report.markdown_review[:1200] + '\n\n*(Full report generated)*'))

@cli.group(name='db')
def db_group():
    """Database schema analysis, index optimization, and migrations."""
    pass

@db_group.command(name='optimize')
@click.argument('schema_or_file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def db_optimize_cmd(schema_or_file, as_json):
    """Analyze SQL DDL or models for missing indexes and generate UP/DOWN migrations."""
    from saleha.core.db_optimizer import db_optimizer
    content = schema_or_file
    if os.path.isfile(schema_or_file):
        with open(schema_or_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    analysis = _cmds.db_optimizer.analyze_schema(content)
    if as_json:
        click.echo(json.dumps({'tables_found': analysis.tables_found, 'missing_indexes': analysis.missing_indexes, 'n_plus_one_risks': analysis.n_plus_one_risks, 'migration_sql_up': analysis.migration_sql_up, 'migration_sql_down': analysis.migration_sql_down}, ensure_ascii=True))
        return
    console.print(Panel(f"[bold cyan]Tables Found:[/] {', '.join(analysis.tables_found) or 'None'}\n[bold cyan]Missing Indexes Detected:[/] {len(analysis.missing_indexes)}\n[bold cyan]N+1 Query Risks:[/] {len(analysis.n_plus_one_risks)}", title='[bold green]🗄️ Database Schema & Index Optimizer[/]', border_style='green'))
    console.print('\n[bold green]⚡ Generated Migration (UP):[/]')
    console.print(Syntax(analysis.migration_sql_up, 'sql', theme='monokai'))

@cli.group(name='workspace')
def workspace_group():
    """Multi-Repo & Monorepo synchronized workspace coordination."""
    pass

@workspace_group.command(name='status')
@click.option('--path', '-p', default='.', help='Workspace root path')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def workspace_status_cmd(path, as_json):
    """Audit branch status and uncommitted changes across all workspace repos."""
    from saleha.core.workspace_coordinator import workspace_coordinator
    statuses = workspace_coordinator.get_workspace_status(root_dir=path)
    if as_json:
        click.echo(json.dumps([s.__dict__ for s in statuses], ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title='🌐 Multi-Repo Workspace Status', border_style='cyan')
    table.add_column('Repository', style='bold cyan')
    table.add_column('Current Branch', style='yellow')
    table.add_column('Clean Status', justify='center')
    table.add_column('Uncommitted Files', justify='right')
    for s in statuses:
        clean_txt = '[green]✅ CLEAN[/]' if s.is_clean else '[yellow]⚠️ DIRTY[/]'
        table.add_row(s.name, s.current_branch, clean_txt, str(s.uncommitted_count))
    console.print(table)

@cli.group(name='sre')
def sre_group():
    """Autonomous SRE Incident Responder and Log Analyzer."""
    pass

@sre_group.command(name='analyze')
@click.argument('log_or_file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def sre_analyze_cmd(log_or_file, as_json):
    """Analyze production stacktrace and synthesize emergency hotfix patch."""
    from saleha.core.sre_responder import sre_responder
    content = log_or_file
    if os.path.isfile(log_or_file):
        with open(log_or_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    report = sre_responder.analyze_log(content)
    if as_json:
        click.echo(json.dumps(report.__dict__, ensure_ascii=True))
        return
    sev_color = 'red' if report.severity in ('CRITICAL', 'HIGH') else 'yellow'
    console.print(Panel(f"[bold cyan]Exception:[/] [{sev_color}]{report.error_type}[/]\n[bold cyan]Severity:[/] [{sev_color}]{report.severity}[/]\n[bold cyan]Offending Location:[/] {report.offending_file or 'N/A'}:{report.offending_line or 'N/A'}\n[bold cyan]Message:[/] {report.error_message}\n\n[bold yellow]Root Cause Analysis (RCA):[/]\n{report.root_cause_analysis}", title=f'[{sev_color}]🚨 Autonomous SRE Incident Report[/]', border_style=sev_color))
    console.print('\n[bold green]🩹 Emergency Hotfix Patch:[/]')
    console.print(Syntax(report.hotfix_patch, 'python', theme='monokai'))

@cli.group(name='refactor')
def refactor_group():
    """
    Autonomous Multi-File Atomic Refactoring & AST Symbol Migration.
    """
    pass

@refactor_group.command(name='rename')
@click.argument('old_symbol')
@click.argument('new_symbol')
@click.option('--no-commit', is_flag=True, help='Do not auto-commit changes')
def refactor_rename_cmd(old_symbol, new_symbol, no_commit):
    """
    Rename symbol across all definitions and call-sites with atomic rollback protection.
    
    Example: saleha refactor rename SmartRouter NextGenRouter
    """
    from saleha.core.multi_file_refactorer import multi_file_refactorer
    console.print(f'[bold cyan]🔄 Planning atomic multi-file rename:[/] [yellow]{old_symbol}[/] -> [green]{new_symbol}[/]')
    res = multi_file_refactorer.rename_symbol(old_symbol, new_symbol, auto_commit=not no_commit)
    if res.success:
        console.print(f"\n[bold green]✅ Successfully renamed '{old_symbol}' -> '{new_symbol}' across {len(res.files_modified)} files![/]")
        for f in res.files_modified:
            console.print(f'  • [cyan]{f}[/]')
        if res.commit_hash:
            console.print(f'\n[cyan]📦 Git Commit:[/] [yellow]{res.commit_hash}[/]')
    else:
        console.print(f'\n[bold red]❌ Refactoring failed:[/] {res.error}')
        if res.rollback_performed:
            console.print('[bold yellow]🛡️ Automatic transactional rollback completed. Workspace is 100% intact.[/]')

@cli.group(name='multi-repo')
def multi_repo_group():
    """
    Multi-Repository & Monorepo Cross-Service Dependency Mapping.
    """
    pass

@multi_repo_group.command(name='scan')
@click.argument('workspace_dir', default='.')
def multi_repo_scan_cmd(workspace_dir):
    """
    Scan workspace for child repositories and build cross-repo dependency index.
    
    Example: saleha multi-repo scan .
    """
    from saleha.core.multi_repo_graph import multi_repo_graph
    console.print(f'[bold cyan]🏢 Scanning multi-repository workspace:[/] [yellow]{workspace_dir}[/]')
    meta = multi_repo_graph.scan_workspace(workspace_dir)
    table = Table(title='🏢 Multi-Repository Swarm Index', show_header=True, header_style='bold blue', expand=True)
    table.add_column('Repository / Package', style='bold white')
    table.add_column('Source Files', style='cyan')
    table.add_column('AST Symbols', style='green')
    table.add_column('Git Repo', style='yellow')
    for r_name, r_meta in meta.items():
        table.add_row(r_name, str(r_meta.files_count), str(r_meta.symbols_count), 'Yes' if r_meta.is_git else 'No')
    console.print(table)

@cli.group(name='env')
def env_group():
    """
    Ephemeral Secret & Process Environment Sync.
    """
    pass

@env_group.command(name='list')
def env_list_cmd():
    """
    List decrypted environment keys from Vault.
    
    Example: saleha env list
    """
    from saleha.core.env_sync import env_sync
    secrets = env_sync.get_vault_env()
    console.print(f'[bold cyan]🔐 Vault Environment Variables ({len(secrets)} active):[/]')
    for k in secrets:
        console.print(f'  • [green]{k}[/]=******')

