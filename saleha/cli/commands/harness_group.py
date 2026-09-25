"""`saleha harness` commands (auto-extracted from the former monolithic
saleha/cli/commands.py).

Imports `cli` to register commands against the same Click group. The harness
modules are imported inside each command so `saleha --help` stays fast.
"""
import json

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from saleha.cli.commands import cli, console


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
    table = Table(title='Saleha Harness Benchmark Datasets', border_style='cyan')
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
@click.option('--dry-run', is_flag=True, help='List the tasks that would run; generates and scores nothing')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def harness_run_cmd(benchmark, model, limit, workers, output_file, dry_run, as_json):
    """Run multi-domain model evaluation and compute Pass@1 over executed tasks."""
    from rich.markup import escape

    from saleha.harness import harness, reporter
    try:
        with Progress(SpinnerColumn(), TextColumn(f"[cyan]Executing Saleha Harness on '{model}' (Suite: {benchmark})..."), console=console, transient=True) as progress:
            progress.add_task('harness', total=None)
            report = harness.evaluate(model=model, benchmark=benchmark, limit=limit, workers=workers, dry_run=dry_run)
    except ValueError as e:
        raise click.ClickException(str(e)) from None
    if as_json:
        payload = {'model': report.model_name, 'timestamp': report.timestamp, 'dry_run': report.dry_run, 'saved_to_history': report.saved, 'total_tasks': report.total_tasks, 'executed_tasks': report.executed_tasks, 'passed_tasks': report.passed_tasks, 'overall_pass_at_1': report.overall_pass_at_1, 'avg_latency_sec': report.avg_latency_sec, 'planned_tasks': report.planned_tasks, 'benchmarks': {k: {'total': v.total_tasks, 'executed': v.executed_tasks, 'passed': v.passed_tasks, 'pass_at_1': v.pass_at_1, 'avg_latency': v.avg_latency_sec, 'not_run': {t.task_id: t.error_detail for t in v.task_results if not t.executed}} for k, v in report.benchmark_summaries.items()}}
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    if report.dry_run:
        table = Table(title=f'Harness dry run -- model: {report.model_name}', border_style='yellow')
        table.add_column('Benchmark Suite', style='bold cyan')
        table.add_column('Tasks That Would Run')
        for name, ids in report.planned_tasks.items():
            table.add_row(name, ', '.join(ids))
        console.print(table)
        console.print(f'[yellow]Dry run: {report.total_tasks} task(s) selected, nothing generated or executed, no score, not saved to history.[/]')
    else:
        table = Table(title=f'Saleha Harness Evaluation -- Model: {report.model_name}', border_style='green')
        table.add_column('Benchmark Suite', style='bold cyan')
        table.add_column('Tasks', justify='right')
        table.add_column('Executed', justify='right')
        table.add_column('Passed', justify='right')
        table.add_column('Pass@1', justify='right', style='bold green')
        table.add_column('Avg Latency', justify='right', style='yellow')
        for name, summ in report.benchmark_summaries.items():
            pct = 'n/a' if summ.pass_at_1 is None else f'{summ.pass_at_1}%'
            table.add_row(name, str(summ.total_tasks), str(summ.executed_tasks), str(summ.passed_tasks), pct, f'{summ.avg_latency_sec}s')
        console.print(table)
        overall = 'n/a (no task executed)' if report.overall_pass_at_1 is None else f'{report.overall_pass_at_1}%'
        not_run = report.total_tasks - report.executed_tasks
        saved = 'saved to leaderboard history' if report.saved else 'NOT saved to leaderboard history'
        console.print(Panel(
            f'[bold cyan]Model:[/] {escape(report.model_name)}\n'
            f'[bold cyan]Pass@1:[/] [bold green]{overall}[/] ({report.passed_tasks}/{report.executed_tasks} executed)\n'
            f'[bold cyan]Not run:[/] {not_run} task(s)\n'
            f'[bold cyan]Average Latency:[/] {report.avg_latency_sec}s / executed task\n'
            f'[dim]{saved}[/]',
            title='[bold green]Harness Evaluation Summary[/]', border_style='green'))
        for summ in report.benchmark_summaries.values():
            for t in summ.task_results:
                if not t.executed:
                    console.print(f'[yellow]NOT RUN[/] {t.task_id}: {escape(t.error_detail or "")}')
    if output_file:
        if reporter.export_markdown(report, output_file):
            console.print(f'[bold green]Markdown report exported to:[/] {output_file}')
        else:
            console.print(f'[red]Could not write Markdown report to:[/] {output_file}')

@harness_group.command(name='leaderboard')
def harness_leaderboard_cmd():
    """Display persistent model ranking leaderboard."""
    from saleha.harness import reporter
    reporter.render_leaderboard()

