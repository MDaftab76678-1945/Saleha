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

@cli.group(name='harness')
def harness_group():
    """Industrial-Strength Model Evaluation Framework (DeepSeek Harness standard)."""
    pass

@harness_group.command(name='list')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def harness_list_cmd(as_json):
    """List available benchmark datasets in the harness catalog."""
    from saleha.harness.benchmarks import BenchmarkCatalog
    catalogs = BenchmarkCatalog.list_available_benchmarks()
    if as_json:
        click.echo(json.dumps(catalogs, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title='📚 Saleha Harness Benchmark Datasets', border_style='cyan')
    table.add_column('Benchmark Suite', style='bold cyan')
    table.add_column('Tasks', justify='right', style='green')
    table.add_column('Domain Category', style='yellow')
    categories = {'humaneval_plus': 'Algorithmic Code Synthesis & Edge-Case Validation', 'mbpp_plus': 'Mostly Basic Python Real-World Utility Problems', 'math_reasoning': 'DeepSeek-R1 Style Multi-Step Mathematical & Algorithmic Reasoning', 'swe_repo': 'Repository-Level Bug Fixing & Deep Config Merging', 'tool_use': 'Agentic Tool Calling & JSON-RPC MCP Function Calling'}
    for name, count in catalogs.items():
        table.add_row(name, str(count), categories.get(name, 'General'))
    console.print(table)

@harness_group.command(name='run')
@click.option('--benchmark', '-b', default='all', help='Benchmark suite to evaluate (humaneval_plus, mbpp_plus, math_reasoning, swe_repo, tool_use, all)')
@click.option('--model', '-m', default='auto', help='Model to evaluate')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of tasks evaluated')
@click.option('--workers', '-w', default=4, type=int, help='Parallel evaluation workers')
@click.option('--output-file', '-o', default=None, help='File path to export Markdown evaluation report')
@click.option('--dry-run', is_flag=True, help='Simulate harness evaluation without LLM calls')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def harness_run_cmd(benchmark, model, limit, workers, output_file, dry_run, as_json):
    """Run comprehensive multi-domain model evaluation and compute Pass@k metrics."""
    from saleha.harness import harness, reporter
    with Progress(SpinnerColumn(), TextColumn(f"[cyan]Executing Saleha Harness on '{model}' (Suite: {benchmark})..."), console=console) as progress:
        progress.add_task('harness', total=None)
        report = harness.evaluate(model=model, benchmark=benchmark, limit=limit, workers=workers, dry_run=dry_run)
    if as_json:
        payload = {'model': report.model_name, 'timestamp': report.timestamp, 'total_tasks': report.total_tasks, 'overall_pass_at_1': report.overall_pass_at_1, 'overall_pass_at_5': report.overall_pass_at_5, 'avg_latency_sec': report.avg_latency_sec, 'avg_tokens_per_sec': report.avg_tokens_per_sec, 'benchmarks': {k: {'total': v.total_tasks, 'passed': v.passed_tasks, 'pass_at_1': v.pass_at_1, 'avg_latency': v.avg_latency_sec} for k, v in report.benchmark_summaries.items()}}
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title=f'🧪 Saleha Harness Evaluation — Model: {report.model_name}', border_style='green')
    table.add_column('Benchmark Suite', style='bold cyan')
    table.add_column('Tasks', justify='right')
    table.add_column('Passed', justify='right')
    table.add_column('Pass@1', justify='right', style='bold green')
    table.add_column('Avg Latency', justify='right', style='yellow')
    for name, summ in report.benchmark_summaries.items():
        table.add_row(name, str(summ.total_tasks), str(summ.passed_tasks), f'{summ.pass_at_1}%', f'{summ.avg_latency_sec}s')
    console.print(table)
    console.print(Panel(f'[bold cyan]Model:[/] {report.model_name}\n[bold cyan]Overall Pass@1:[/] [bold green]{report.overall_pass_at_1}%[/]\n[bold cyan]Unbiased Pass@5 Estimate:[/] [bold green]{report.overall_pass_at_5}%[/]\n[bold cyan]Average Latency:[/] {report.avg_latency_sec}s / task\n[bold cyan]Throughput:[/] {report.avg_tokens_per_sec} tok/sec', title='[bold green]🏆 Harness Evaluation Summary[/]', border_style='green'))
    if output_file:
        reporter.export_markdown(report, output_file)
        console.print(f'[bold green]💾 Markdown report exported to:[/] {output_file}')

@harness_group.command(name='leaderboard')
def harness_leaderboard_cmd():
    """Display persistent model ranking leaderboard."""
    from saleha.harness import reporter
    reporter.render_leaderboard()

