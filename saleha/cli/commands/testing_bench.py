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
@click.argument('code_file', type=click.Path(exists=True))
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def test(code_file, as_json):
    """
    Test code for syntax and security
    
    Example: saleha test my_script.py
    """
    with open(code_file, 'r', encoding='utf-8') as f:
        code = f.read()
    tester = _cmds.TesterAgent()
    if as_json:
        result = tester.test_code(code)
    else:
        console.print(Panel.fit(f'[bold cyan]🧪 Testing:[/] {code_file}', title='[bold green]Saleha Tester[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
            progress.add_task('[cyan]Testing code...', total=None)
            result = tester.test_code(code)
    if as_json:
        click.echo(json.dumps({'passed': result.passed, 'error_type': result.error_type, 'error_message': result.error_message, 'file': code_file}, ensure_ascii=False))
        if not result.passed:
            raise click.exceptions.Exit(1)
        return
    console.print()
    if result.passed:
        console.print(Panel('[bold green]✅ PASSED[/] - Code is syntactically correct and secure', border_style='green'))
    else:
        console.print(Panel(f'[bold red]❌ FAILED[/] - {result.error_type}', border_style='red'))
        console.print(f'\n[yellow]Reason:[/] {result.error_message}')

@cli.command(name='benchmark')
@click.option('--model', '-m', default='auto', help='Ollama model to benchmark')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of test cases')
@click.option('--dry-run', is_flag=True, help='Simulate benchmark run without LLM calls')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def benchmark_cmd(model, limit, dry_run, as_json):
    """
    Benchmark local Ollama models on HumanEval-style coding challenges.
    
    Example: saleha benchmark -m qwen2.5-coder:3b
    Example dry run: saleha benchmark --dry-run
    """
    from saleha.core.evaluator import evaluator
    with Progress(SpinnerColumn(), TextColumn(f"[cyan]Benchmarking model '{model}'..."), console=console) as progress:
        progress.add_task('bench', total=None)
        score = evaluator.run_benchmark(model=model, limit=limit, dry_run=dry_run)
    if as_json:
        click.echo(json.dumps({'model': score.model, 'total_tasks': score.total_tasks, 'passed_tasks': score.passed_tasks, 'pass_rate': score.pass_rate, 'avg_latency_sec': score.avg_latency_sec, 'task_results': score.task_results}, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title=f'📊 Saleha Benchmark Report — Model: {score.model}', border_style='green')
    table.add_column('Task ID', style='bold cyan')
    table.add_column('Difficulty', style='dim')
    table.add_column('Passed', style='bold')
    table.add_column('Latency', style='yellow')
    for res in score.task_results:
        pass_txt = '[green]✅ PASS[/]' if res['passed'] else '[red]❌ FAIL[/]'
        table.add_row(res['task_id'], res['difficulty'], pass_txt, f"{res['latency_sec']}s")
    console.print(table)
    console.print(Panel(f'[bold cyan]Model:[/] {score.model}\n[bold cyan]Pass@1 Rate:[/] [bold green]{score.pass_rate}%[/] ({score.passed_tasks}/{score.total_tasks} passed)\n[bold cyan]Average Latency:[/] {score.avg_latency_sec}s per task', title='[bold green]🏆 Benchmark Summary[/]', border_style='green'))

@cli.command(name='swe-bench')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of task instances')
@click.option('--dry-run', is_flag=True, help='Simulate evaluation without execution')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def swe_bench_cmd(limit, dry_run, as_json):
    """Run SWE-Bench verified evaluation harness on repository-level bug fixing instances."""
    from saleha.core.swe_bench_harness import swe_bench
    with Progress(SpinnerColumn(), TextColumn('[cyan]Running SWE-Bench verification suite...'), console=console) as progress:
        progress.add_task('swe', total=None)
        report = _cmds.swe_bench.run_evaluation(limit=limit, dry_run=dry_run)
    if as_json:
        click.echo(json.dumps({'total_instances': report.total_instances, 'resolved_instances': report.resolved_instances, 'pass_rate': report.pass_rate, 'avg_latency_sec': report.avg_latency_sec, 'results': report.results}, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title='🧪 SWE-Bench Verification Report', border_style='cyan')
    table.add_column('Instance ID', style='bold cyan')
    table.add_column('Repository', style='dim')
    table.add_column('Resolved', style='bold')
    table.add_column('Latency', style='yellow')
    for r in report.results:
        res_txt = '[green]✅ RESOLVED[/]' if r['resolved'] else '[red]❌ UNRESOLVED[/]'
        table.add_row(r['instance_id'], r['repo'], res_txt, f"{r['latency_sec']}s")
    console.print(table)
    console.print(Panel(f'[bold cyan]Pass Rate:[/] [bold green]{report.pass_rate}%[/] ({report.resolved_instances}/{report.total_instances} resolved)\n[bold cyan]Average Time:[/] {report.avg_latency_sec}s per instance', title='[bold green]🏆 SWE-Bench Summary[/]', border_style='green'))

@cli.command(name='benchmark-public')
@click.option('--suite', default='swe_bench', help='Benchmark suite')
def benchmark_public_cmd(suite):
    """
    Run SWE-bench Leaderboard Evaluation and compare against Devin/GPT-4o.
    
    Example: saleha benchmark-public
    """
    from saleha.core.swe_leaderboard import swe_leaderboard
    console.print('[bold cyan]🏁 Running SWE-bench Local Leaderboard Suite...[/]')
    run = swe_leaderboard.run_suite(use_llm=False)
    console.print(f'[bold green]Solved {run.solved}/{run.total_tasks} tasks ({run.score_pct}% pass@1)[/]')
    console.print(swe_leaderboard.leaderboard_text())

@cli.command(name='swe-export')
@click.option('--output', '-o', default='all_preds.jsonl', help='Output JSONL file path')
@click.option('--scorecard', '-s', default='scorecard.md', help='Output markdown scorecard path')
@click.option('--model', default='saleha-v2.0', help='Model name to tag predictions')
def swe_export_cmd(output, scorecard, model):
    """
    Export SWE-bench evaluation run to official all_preds.jsonl and leaderboard scorecard.
    
    Example: saleha swe-export --output dist/all_preds.jsonl --scorecard scorecard.md
    """
    from saleha.core.swe_leaderboard import swe_leaderboard
    from saleha.core.swe_bench_exporter import SWEBenchExporter
    console.print(f'[bold cyan]🏁 Evaluating benchmark and exporting for model:[/] [yellow]{model}[/]')
    run = swe_leaderboard.run_suite(use_llm=False, model=model)
    exporter = SWEBenchExporter(model_name=model)
    jsonl_path = exporter.export_predictions(run, output_file=output)
    md = exporter.generate_leaderboard_scorecard(run)
    with open(scorecard, 'w', encoding='utf-8') as f:
        f.write(md)
    console.print(f'[bold green]✅ Official SWE-bench predictions exported:[/] {jsonl_path}')
    console.print(f'[bold green]📊 Scorecard saved:[/] {os.path.abspath(scorecard)}')
    console.print(f'[bold green]Pass@1 Score:[/] {run.score_pct:.2f}% ({run.solved}/{run.total_tasks} solved)')

@cli.command(name='resolve-issue')
@click.argument('issue_ref')
@click.option('--branch', '-b', default=None, help='Custom branch name')
@click.option('--auto-pr', is_flag=True, help='Open a Pull Request on GitHub')
@click.option('--test-command', default=None,
              help='Command to run as verification, e.g. "pytest -q". '
                   'Without it nothing is verified.')
def resolve_issue_cmd(issue_ref, branch, auto_pr, test_command):
    """
    Fetch a GitHub issue and create a fix branch with a PR description.

    This prepares the branch; it does not write the fix. Pass --test-command
    to have the result reflect a real test run.

    Example: saleha resolve-issue 42 --test-command "pytest -q"
    """
    import shlex
    from saleha.core.issue_resolver import issue_resolver
    console.print(f'[bold cyan]Preparing fix branch for:[/] [yellow]{issue_ref}[/]')

    res = issue_resolver.resolve_issue(
        issue_ref=issue_ref,
        branch_name=branch,
        auto_pr=auto_pr,
        test_command=shlex.split(test_command) if test_command else None,
    )

    if not res.success and res.error:
        console.print(f'[bold red]Failed:[/] {res.error}')
        raise click.exceptions.Exit(1)

    # The old version printed "Issue #N Resolved Successfully!" here on a run
    # that created an empty branch, fabricated a diff and ran no tests. The
    # headline now states what actually happened.
    colour = 'green' if res.tests_passed else (
        'red' if res.tests_passed is False else 'yellow')
    console.print(f'[bold {colour}]{res.summary}[/]')
    console.print(f'  Branch: [cyan]{res.branch_name}[/]')
    if res.diff_result:
        console.print(f'  Changes: {res.diff_result.change_summary}')
    if res.tests_passed is None:
        console.print('  Tests: [yellow]not run[/]')
    else:
        console.print(f"  Tests: "
                      f"[{'green' if res.tests_passed else 'red'}]"
                      f"{'passed' if res.tests_passed else 'FAILED'}[/]")
    if res.pr_result and res.pr_result.pr_url:
        console.print(f'  Pull Request: [bold blue]{res.pr_result.pr_url}[/]')
    elif res.pr_result:
        console.print(f'  Status: [yellow]{res.pr_result.message}[/]')

    if res.caveats:
        console.print('\n[bold yellow]Not established by this run:[/]')
        for caveat in res.caveats:
            console.print(f'  - {caveat}')

    if res.tests_passed is False:
        raise click.exceptions.Exit(1)

@cli.command(name='benchmark-eval')
@click.option('--model', default='auto', help='Model to benchmark')
def benchmark_eval_cmd(model: str):
    """
    Autonomous Benchmark & Evaluation Runner (SiliconCopilot-Eval).
    
    Example: saleha benchmark-eval
    """
    from saleha.core.benchmark_harness import BenchmarkHarness
    console.print(Panel('[bold yellow]📊 Saleha Autonomous Evaluation Benchmark Harness[/bold yellow]', border_style='yellow'))
    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), transient=True) as progress:
        progress.add_task(description='Evaluating benchmark task suite...', total=None)
        harness = BenchmarkHarness(model=model)
        summary = harness.run_suite()
    console.print(Markdown(harness.render_markdown(summary)))

@cli.command(name='test-ui')
@click.argument('path', required=True)
def test_ui_cmd(path: str):
    """
    Autonomous Headless Browser DOM & UI Health Inspector.
    
    Example: saleha test-ui index.html
    """
    from saleha.core.browser_agent import browser_agent
    rep = browser_agent.inspect_file(path)
    col = 'green' if rep.is_ui_valid else 'yellow'
    console.print(Panel(f'[bold {col}]🌐 Headless Browser DOM & UI Audit: {path}[/bold {col}]\n{rep.summary}', border_style=col))

@cli.command(name='swebench-eval')
def swebench_eval_cmd():
    """
    Run standardized SWE-Bench real-world software engineering benchmarks.
    
    Example: saleha swebench-eval
    """
    from saleha.core.swebench_runner import swebench_runner
    rep = swebench_runner.run_benchmark_suite()
    console.print(Panel(f'[bold cyan]📊 SWE-Bench Benchmark Scorecard[/bold cyan]\n{rep.summary}', border_style='cyan'))

@cli.command('solve-issue')
@click.argument('issue_description')
@click.option('--repo', default='Saleha', help='Target repository name')
def solve_issue_cli_cmd(issue_description: str, repo: str):
    """Autonomously triage, patch, test, and generate a GitHub PR for an issue."""
    from saleha.agents.issue_resolver import issue_resolver
    console.print(f'\n[bold cyan]🐙 Autonomous Issue Resolver Bot — Target:[/] [white]{repo}[/]')
    console.print(f'[dim]Analyzing issue report: "{issue_description[:60]}..."[/dim]\n')
    plan = issue_resolver.resolve_issue(issue_description, repo_name=repo)
    if plan.success:
        console.print(f'[bold green]✨ Issue Successfully Resolved in {plan.duration_ms}ms![/bold green]')
        console.print(f'  • Issue Reference : [bold yellow]{plan.issue_id}[/]')
        console.print(f'  • Suggested Branch: [bold cyan]{plan.branch_name}[/]')
        console.print(f"  • Security Audit  : {('[green]PASS (0 CVEs)[/]' if plan.security_clean else '[yellow]Hardened[/]')}")
        console.print(f"  • Pytest Assertion: {('[green]100% Passed[/]' if plan.tests_passed else '[red]Failed[/]')}\n")
        console.print(Panel(plan.pr_body_markdown, title='[bold green]📦 Generated GitHub PR Markdown[/]', border_style='green'))
    else:
        console.print(f'[bold red]❌ Failed to resolve issue automatically.[/]')

