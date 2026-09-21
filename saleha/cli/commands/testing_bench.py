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
def test(code_file: str, as_json: bool) -> None:
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

# Renamed from 'benchmark'. That name is also declared by
# saleha/cli/benchmark_cli.py (the micro-benchmark suite), and Click keeps
# whichever registers last -- so this command, the one that benchmarks an
# Ollama model on coding tasks, could not be invoked at all. It had been
# unreachable since the CLI monolith was split on 2026-09-06. The two do
# genuinely different things, so the fix is to give this one its own name
# rather than delete either. Pinned by test_cli_reachability.py.
@cli.command(name='benchmark-model')
@click.option('--model', '-m', default='auto', help='Ollama model to benchmark')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of test cases')
@click.option('--dry-run', is_flag=True, help='Simulate benchmark run without LLM calls')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def benchmark_cmd(model: str, limit: int, dry_run: bool, as_json: bool) -> None:
    """
    Benchmark local Ollama models on HumanEval-style coding challenges.
    
    Example: saleha benchmark-model -m qwen2.5-coder:3b
    Example dry run: saleha benchmark-model --dry-run
    """
    from saleha.core.evaluator import evaluator
    with Progress(SpinnerColumn(), TextColumn(f"[cyan]Benchmarking model '{model}'..."), console=console) as progress:
        progress.add_task('bench', total=None)
        score = evaluator.run_benchmark(model=model, limit=limit, dry_run=dry_run)
    if as_json:
        # A dry run executes nothing, so `passed_tasks` stays 0 and
        # `pass_rate` computes to 0.0 -- arithmetically correct, but a script
        # reading this JSON sees a measured 0% rather than "no measurement".
        # The table path below was fixed to say so; this branch returns before
        # reaching it, so it needs the same treatment.
        payload = {
            'model': score.model,
            'total_tasks': score.total_tasks,
            'did_execute': not dry_run,
            'passed_tasks': None if dry_run else score.passed_tasks,
            'pass_rate': None if dry_run else score.pass_rate,
            'avg_latency_sec': None if dry_run else score.avg_latency_sec,
            'task_results': score.task_results,
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title=f'📊 Saleha Benchmark Report — Model: {score.model}', border_style='green')
    table.add_column('Task ID', style='bold cyan')
    table.add_column('Difficulty', style='dim')
    table.add_column('Passed', style='bold')
    table.add_column('Latency', style='yellow')
    for res in score.task_results:
        # `passed` is None on a dry run -- evaluator.py sets it that way
        # deliberately (pass 51 removed a hardcoded True there). None is
        # falsy, so this used to paint every dry-run row a red FAIL: the
        # engine was made honest and the display kept lying, just in the
        # other direction. A task that never ran neither passed nor failed.
        if res['passed'] is None:
            pass_txt = '[dim]not run[/]'
        else:
            pass_txt = '[green]✅ PASS[/]' if res['passed'] else '[red]❌ FAIL[/]'
        table.add_row(res['task_id'], res['difficulty'], pass_txt, f"{res['latency_sec']}s")
    console.print(table)

    # Same reason: pass_rate is computed from a counter that cannot increment
    # when nothing executes, so "0.0%" reads as "the model failed everything"
    # on a run that invoked no model at all.
    if dry_run:
        console.print(Panel(
            f'[bold cyan]Model:[/] {score.model}\n'
            f'[yellow]Nothing was executed (--dry-run), so there is no pass '
            f'rate.[/] {score.total_tasks} task(s) would be attempted.',
            title='[bold yellow]Dry run[/]', border_style='yellow'))
        return
    console.print(Panel(f'[bold cyan]Model:[/] {score.model}\n[bold cyan]Pass@1 Rate:[/] [bold green]{score.pass_rate}%[/] ({score.passed_tasks}/{score.total_tasks} passed)\n[bold cyan]Average Latency:[/] {score.avg_latency_sec}s per task', title='[bold green]🏆 Benchmark Summary[/]', border_style='green'))

@cli.command(name='sandbox-selfcheck')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of instances')
@click.option('--list-only', is_flag=True, help='List the instances without executing them')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def sandbox_selfcheck_cmd(limit: int, list_only: bool, as_json: bool) -> None:
    """Check the sandbox executes known-good code and observes its output.

    This is not a benchmark. The instances are pre-written correct code, no
    model is invoked, and nothing is fixed -- so it measures the executor,
    not the agent. For a real capability measurement run
    `python scripts/measure_real_pass_rate.py`.
    """
    with Progress(SpinnerColumn(), TextColumn('[cyan]Running sandbox self-check...'), console=console) as progress:
        progress.add_task('selfcheck', total=None)
        report = _cmds.sandbox_self_check.run_self_check(limit=limit, list_only=list_only)
    if as_json:
        click.echo(json.dumps({'total_instances': report.total_instances, 'executed_ok': report.executed_ok, 'did_execute': report.did_execute, 'avg_latency_sec': report.avg_latency_sec, 'results': report.results}, ensure_ascii=True))
        return
    from rich.table import Table
    table = Table(title='Sandbox self-check', border_style='cyan')
    table.add_column('Instance ID', style='bold cyan')
    table.add_column('Source', style='dim')
    table.add_column('Executed cleanly', style='bold')
    table.add_column('Latency', style='yellow')
    for r in report.results:
        if r['executed_ok'] is None:
            res_txt = '[dim]not run[/]'
        else:
            res_txt = '[green]yes[/]' if r['executed_ok'] else '[red]NO[/]'
        table.add_row(r['instance_id'], r['repo'], res_txt, f"{r['latency_sec']}s")
    console.print(table)
    if not report.did_execute:
        console.print(Panel('[yellow]Nothing was executed (--list-only), so there is no result.[/]', border_style='yellow'))
        return
    console.print(Panel(f'[bold cyan]Executed cleanly:[/] {report.executed_ok}/{report.total_instances}\n[bold cyan]Average time:[/] {report.avg_latency_sec}s per instance\n[dim]Executor check only -- no model invoked, no bug fixed.[/]', border_style='cyan'))

@cli.command(name='benchmark-local')
@click.option('--model', '-m', default=None, help='Ollama model to benchmark')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of tasks')
@click.option('--preflight', is_flag=True, help='Only check that every test can fail')
def benchmark_local_cmd(model: str, limit: int, preflight: bool) -> None:
    """Run Saleha's local task benchmark against a real model.

    Twelve small self-contained problems, each with a test verified to fail
    on wrong code before the run starts. Not SWE-bench, not a leaderboard.

    Example: saleha benchmark-local -m qwen2.5-coder:3b
    """
    from saleha.core.real_task_bench import DEFAULT_MODEL
    from saleha.core.swe_leaderboard import local_benchmark

    if preflight:
        pre = local_benchmark.preflight()
        if pre['usable']:
            console.print(f"[green]All {pre['total_tasks']} tests fail on wrong code, as they must.[/]")
        else:
            console.print(f"[red]These tests cannot fail, so they measure nothing:[/] {pre['tests_that_cannot_fail']}")
            raise click.exceptions.Exit(1)
        return

    chosen = model or DEFAULT_MODEL
    console.print(f'[cyan]Running local task benchmark against[/] [yellow]{chosen}[/][cyan]...[/]')

    def _report(outcome):
        mark = '[green]PASS[/]' if outcome.passed else '[red]FAIL[/]'
        detail = f'  {outcome.error}' if outcome.error else ''
        console.print(f'  {outcome.task_id:<24} {mark}  ({outcome.duration_sec}s){detail}')

    run = local_benchmark.run_suite(model=chosen, limit=limit, on_task=_report)

    if not run.metadata.get('did_run', True):
        console.print(Panel(f'[yellow]Benchmark did not run.[/]\n{run.notes}', border_style='yellow'))
        raise click.exceptions.Exit(1)

    console.print(Panel(
        f'[bold cyan]Passed:[/] {run.solved}/{run.total_tasks}  '
        f'([bold]{run.score_pct:.1f}%[/])\n'
        f'[bold cyan]Model:[/] {run.model}\n'
        f'[dim]Twelve small self-contained problems on one machine. '
        f'Not SWE-bench, not a leaderboard position.[/]',
        border_style='cyan'))


@cli.command(name='benchmark-public')
def benchmark_public_cmd() -> None:
    """Show Saleha's best recorded local score, and published SWE-bench figures.

    The two are reported separately on purpose: Saleha has not run SWE-bench
    Verified, so its local score is not comparable to those figures.

    Example: saleha benchmark-public
    """
    from saleha.core.real_task_bench import scored_swebench_availability
    from saleha.core.swe_leaderboard import local_benchmark

    console.print(local_benchmark.leaderboard_text())
    available, detail = scored_swebench_availability()
    if available:
        console.print(f'\n[green]Scored SWE-bench is available here:[/] {detail}')
    else:
        console.print(f'\n[yellow]Scored SWE-bench cannot run here:[/] {detail}')


@cli.command(name='swe-export')
@click.option('--output', '-o', default='all_preds.jsonl', help='Output JSONL file path')
@click.option('--scorecard', '-s', default='scorecard.md', help='Output markdown scorecard path')
@click.option('--model', '-m', default=None, help='Model to run and tag predictions with')
def swe_export_cmd(output: str, scorecard: str, model: str) -> None:
    """Run the local benchmark and export predictions plus a scorecard.

    The JSONL is in SWE-bench submission format. The scorecard reports the
    run's real numbers and states plainly which benchmark produced them --
    it does not present a local score as a SWE-bench result.

    Example: saleha swe-export -o dist/all_preds.jsonl
    """
    from saleha.core.real_task_bench import DEFAULT_MODEL
    from saleha.core.swe_bench_exporter import SWEBenchExporter
    from saleha.core.swe_leaderboard import local_benchmark

    chosen = model or DEFAULT_MODEL
    console.print(f'[cyan]Running local benchmark for[/] [yellow]{chosen}[/][cyan]...[/]')

    def _report(outcome):
        mark = '[green]PASS[/]' if outcome.passed else '[red]FAIL[/]'
        console.print(f'  {outcome.task_id:<24} {mark}  ({outcome.duration_sec}s)')

    run = local_benchmark.run_suite(model=chosen, on_task=_report)
    exporter = SWEBenchExporter(model_name=chosen)
    jsonl_path = exporter.export_predictions(
        run, output_file=output, task_results=local_benchmark.task_results(run))
    md = exporter.generate_scorecard(run)
    with open(scorecard, 'w', encoding='utf-8') as f:
        f.write(md)

    console.print(f'[green]Predictions written:[/] {jsonl_path}')
    console.print(f'[green]Scorecard written:[/] {os.path.abspath(scorecard)}')
    if run.metadata.get('did_run', True):
        console.print(f'[cyan]Local pass rate:[/] {run.score_pct:.2f}% '
                      f'({run.solved}/{run.total_tasks}) -- not a SWE-bench score.')
    else:
        console.print(f'[yellow]Benchmark did not run:[/] {run.notes}')


@cli.command(name='resolve-issue')
@click.argument('issue_ref')
@click.option('--branch', '-b', default=None, help='Custom branch name')
@click.option('--auto-pr', is_flag=True, help='Open a Pull Request on GitHub')
@click.option('--test-command', default=None,
              help='Command to run as verification, e.g. "pytest -q". '
                   'Without it nothing is verified.')
@click.option('--agent', is_flag=True, help='Run autonomous AgentLoop solver to write and verify the fix')
@click.option('--model', '-m', default='auto', help='Model to use with --agent')
def resolve_issue_cmd(issue_ref: str, branch: str, auto_pr: bool, test_command: str,
                      agent: bool, model: str) -> None:
    """
    Fetch a GitHub issue and create a fix branch with a PR description.

    Pass --agent to have Saleha autonomously investigate, patch, and verify the fix.
    Pass --test-command to have the result reflect a real test run.

    Example: saleha resolve-issue 42 --test-command "pytest -q" --agent
    """
    import shlex
    from saleha.core.issue_resolver import issue_resolver
    console.print(f'[bold cyan]Preparing fix branch for:[/] [yellow]{issue_ref}[/]')

    res = issue_resolver.resolve_issue(
        issue_ref=issue_ref,
        branch_name=branch,
        auto_pr=auto_pr,
        test_command=shlex.split(test_command) if test_command else None,
        autonomous=agent,
        model=model,
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
def benchmark_eval_cmd(model: str) -> None:
    """
    Autonomous Benchmark & Evaluation Runner (SiliconCopilot-Eval).
    
    Example: saleha benchmark-eval
    """
    from saleha.core.harness.benchmark_harness import BenchmarkHarness
    console.print(Panel('[bold yellow]📊 Saleha Autonomous Evaluation Benchmark Harness[/bold yellow]', border_style='yellow'))
    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), transient=True) as progress:
        progress.add_task(description='Evaluating benchmark task suite...', total=None)
        harness = BenchmarkHarness(model=model)
        summary = harness.run_suite()
    console.print(Markdown(harness.render_markdown(summary)))

@cli.command(name='test-ui')
@click.argument('path', required=True)
def test_ui_cmd(path: str) -> None:
    """
    Autonomous Headless Browser DOM & UI Health Inspector.
    
    Example: saleha test-ui index.html
    """
    from saleha.core.browser_agent import browser_agent
    rep = browser_agent.inspect_file(path)
    col = 'green' if rep.is_ui_valid else 'yellow'
    console.print(Panel(f'[bold {col}]🌐 Headless Browser DOM & UI Audit: {path}[/bold {col}]\n{rep.summary}', border_style=col))

@cli.command(name='swebench-eval')
def swebench_eval_cmd() -> None:
    """
    Run standardized SWE-Bench real-world software engineering benchmarks.
    
    Example: saleha swebench-eval
    """
    from saleha.core.harness.swebench_runner import swebench_runner
    rep = swebench_runner.run_benchmark_suite()
    console.print(Panel(f'[bold cyan]📊 SWE-Bench Benchmark Scorecard[/bold cyan]\n{rep.summary}', border_style='cyan'))

@cli.command('solve-issue')
@click.argument('issue_description')
@click.option('--repo', default='Saleha', help='Target repository name')
def solve_issue_cli_cmd(issue_description: str, repo: str) -> None:
    """Autonomously triage, patch, test, and generate a GitHub PR for an issue."""
    from saleha.agents.issue_resolver import issue_resolver
    console.print(f'\n[bold cyan]🐙 Autonomous Issue Resolver Bot — Target:[/] [white]{repo}[/]')
    console.print(f'[dim]Analyzing issue report: "{issue_description[:60]}..."[/dim]\n')
    plan = issue_resolver.resolve_issue(issue_description, repo_name=repo)
    if plan.success:
        # This pipeline generates code as a string and never writes it to
        # disk, so nothing was resolved: what finished is a proposed patch
        # plus a PR description. The old headline read "Issue Successfully
        # Resolved", and the test line read "100% Passed" -- a percentage
        # computed nowhere, over a sandbox run of tests this pipeline wrote
        # for its own patch. The PR body itself was corrected earlier; this
        # is the same claim one layer up, in the terminal that prints it.
        console.print(f'[bold green]Patch and PR description generated in {plan.duration_ms}ms[/bold green]')
        console.print(f'  • Issue Reference : [bold yellow]{plan.issue_id}[/]')
        console.print(f'  • Suggested Branch: [bold cyan]{plan.branch_name}[/] [dim](not created)[/]')
        console.print(f"  • Security Audit  : {('[green]PASS (0 CVEs)[/]' if plan.security_clean else '[yellow]Hardened[/]')}")
        console.print(f"  • Generated tests : {('[green]passed in sandbox[/]' if plan.tests_passed else '[red]FAILED[/]')}")
        console.print('  [dim]This repository\'s own test suite was not run.[/]\n')
        console.print(Panel(plan.pr_body_markdown, title='[bold green]📦 Generated GitHub PR Markdown[/]', border_style='green'))
    else:
        console.print(f'[bold red]❌ Failed to resolve issue automatically.[/]')

