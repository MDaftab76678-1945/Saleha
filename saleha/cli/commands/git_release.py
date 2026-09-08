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
@click.argument('goal')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
@click.option('--output-dir', type=click.Path(file_okay=False), help='Base directory for the generated project')
def project(goal, model, as_json, output_dir):
    """
    Build a multi-file project (breaks goal into files, generates each)

    Single-file 'run' command ke bajaye ye bade goals ke liye hai jinme
    ek se zyada files chahiye. Har file alag se generate hoti hai aur
    project folder me save hoti hai (~/saleha_projects/<name>/).

    Example: saleha project "A simple command-line calculator"
    """
    builder = _cmds.ProjectBuilder(model=model, projects_dir=output_dir) if output_dir else _cmds.ProjectBuilder(model=model)
    if as_json:
        with contextlib.redirect_stdout(io.StringIO()):
            result = builder.build(goal)
    else:
        console.print(Panel.fit(f'[bold cyan]🏗️ Project Goal:[/] {goal}\n[bold cyan]🤖 Model:[/] {model}', title='[bold green]Saleha Project Builder[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
            progress.add_task('[cyan]Building project...', total=None)
            result = builder.build(goal)
    if as_json:
        click.echo(json.dumps({'success': result.success, 'project_dir': result.project_dir, 'files': [{'filename': file_result.filename, 'tested_ok': file_result.tested_ok, 'test_error': file_result.test_error} for file_result in result.files], 'entry_point': result.entry_point, 'entry_point_ok': result.entry_point_ok, 'entry_point_error': result.entry_point_error, 'log': result.log}, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    console.print()
    if result.success:
        console.print(Panel(f'[bold green]✅ SUCCESS[/] -- {len(result.files)} files created', border_style='green'))
    else:
        console.print(Panel('[bold yellow]⚠️ Partial/Failed[/] -- kuch files me problem hai, neeche dekho', border_style='yellow'))
    console.print(f'\n[bold cyan]📁 Project location:[/] {result.project_dir}\n')
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('File', style='cyan')
    table.add_column('Status', justify='center')
    table.add_column('Note', style='yellow')
    for f in result.files:
        status = '[green]✅[/]' if f.tested_ok else '[red]❌[/]'
        table.add_row(f.filename, status, f.test_error or '-')
    console.print(table)

@cli.command()
@click.argument('goal')
@click.option('--branch', '-b', default=None, help='Custom git branch name')
@click.option('--output-dir', '-o', default=None, type=click.Path(file_okay=False), help='Directory to export PR markdown and artifacts')
@click.option('--debate', is_flag=True, help='Enable multi-agent deliberation debate')
@click.option('--push', is_flag=True, help='Push feature branch to remote origin')
@click.option('--open-remote', is_flag=True, help='Open Pull Request directly on GitHub')
@click.option('--base', default='main', help='Base branch for remote PR')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def pr(goal, branch, output_dir, debate, push, open_remote, base, model, as_json):
    """Autonomously generate git branch, conventional commit, test evidence, and PULL_REQUEST.md."""
    generator = _cmds.PRGenerator(model=model)
    if as_json:
        with contextlib.redirect_stdout(io.StringIO()):
            res = generator.generate_pr(goal=goal, branch_name=branch, output_dir=output_dir, debate=debate, push=push, open_pr=open_remote, base_branch=base)
        payload = {'success': res.success, 'branch_name': res.branch_name, 'commit_title': res.commit_title, 'commit_body': res.commit_body, 'pr_markdown': res.pr_markdown, 'output_dir': res.output_dir, 'test_passed': res.test_passed, 'pr_url': res.pr_url, 'error': res.error}
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not res.success:
            raise click.exceptions.Exit(1)
        return
    console.print(Panel.fit(f"[bold cyan]🎯 Goal:[/] {goal}\n[bold cyan]🌿 Branch:[/] {branch or generator._sanitize_branch_name(goal)}\n[bold cyan]📁 Output Dir:[/] {output_dir or 'Console Only'}\n[bold cyan]☁️ Remote Push:[/] {('Enabled' if push or open_remote else 'Disabled')}", title='[bold green]🚀 Autonomous Git CI/CD & PR Agent[/]', border_style='green'))
    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
        progress.add_task('[cyan]Deliberating, implementing, testing & generating PR...', total=None)
        res = generator.generate_pr(goal=goal, branch_name=branch, output_dir=output_dir, debate=debate, push=push, open_pr=open_remote, base_branch=base)
    if res.success:
        console.print(Panel(f"[bold green]✅ Pull Request Package Ready[/]\n[bold cyan]Branch:[/] {res.branch_name}\n[bold cyan]Commit:[/] {res.commit_title}\n[bold cyan]Remote PR:[/] {res.pr_url or 'Local Only'}", border_style='green'))
        if res.output_dir:
            console.print(f'\n[bold green]📁 Exported PULL_REQUEST.md to:[/] {res.output_dir}')
        else:
            console.print('\n[bold cyan]📄 PULL_REQUEST.md Preview:[/]')
            console.print(Markdown(res.pr_markdown[:800] + '\n\n*(Full markdown generated)*'))
    else:
        console.print(Panel(f'[bold red]❌ PR Generation Failed:[/] {res.error}', border_style='red'))

@cli.command()
@click.option('--hard', is_flag=True, help='Hard reset instead of soft revert')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def undo(hard, as_json):
    """
    Safely undo/rollback the last Saleha Git commit (Aider-style).
    
    Example: saleha undo
    Example hard reset: saleha undo --hard
    """
    from saleha.core.git_native import git_engine
    if hard:
        # --hard destroys uncommitted work, not just the last commit. Say what
        # is at stake before the approval gate asks.
        status = git_engine.get_status_summary()
        dirty = status.get('dirty_count', 0)
        if dirty:
            console.print(f'[bold red]⚠ --hard will permanently destroy {dirty} '
                          f'uncommitted change(s) in the working tree.[/]')
    result = git_engine.rollback_last_commit(soft=not hard)
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=True))
        return
    if result.get('success'):
        console.print(Panel(f"[bold green]✅ Success:[/] {result.get('message')}\n[dim]Reverted:[/] {result.get('reverted_commit')}", title='[bold green]🌿 Saleha Git Undo[/]', border_style='green'))
    else:
        console.print(Panel(f"[bold red]❌ Undo Failed:[/] {result.get('error')}", title='[bold red]🌿 Saleha Git Undo[/]', border_style='red'))

@cli.command(name='pr-review')
@click.argument('base_branch', default='main')
@click.option('--output-file', '-o', default=None, help='Save review markdown report to file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def pr_review_cmd(base_branch, output_file, as_json):
    """Analyze Git PR diff, run SAST security scan, and generate review comments."""
    from saleha.core.pr_reviewer import pr_reviewer
    diff_text = pr_reviewer.get_git_diff(base_branch=base_branch)
    report = pr_reviewer.review_diff(diff_text, pr_title=f'Branch diff against {base_branch}')
    if as_json:
        click.echo(json.dumps({'summary': report.summary, 'risk_level': report.risk_level, 'files_analyzed': report.files_analyzed, 'security_findings': report.security_findings, 'recommendations': report.recommendations, 'merge_decision': report.merge_decision}, ensure_ascii=True))
        return
    console.print(Markdown(report.markdown_report))
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report.markdown_report)
        console.print(f'\n[bold green]💾 Review saved to {output_file}[/]')

@cli.command(name='ship')
@click.argument('target_dir', default='.')
@click.option('--apply', 'auto_apply', is_flag=True, help='Automatically write Dockerfile, compose, and CI workflows')
def ship_cmd(target_dir, auto_apply):
    """
    Synthesize production-hardened multi-stage Dockerfiles, docker-compose, and GitHub Actions CI.
    
    Example: saleha ship . --apply
    """
    from saleha.core.cloud_deployer import cloud_deployer
    plan = _cmds.cloud_deployer.plan_deployment(target_dir)
    console.print(Panel(f'[bold cyan]Target Workspace:[/] {os.path.abspath(target_dir)}\n[bold cyan]Detected Runtime Stack:[/] [bold green]{plan.stack_detected.upper()}[/]\n[bold cyan]Generated Assets:[/] {len(plan.assets)} artifacts', title='[bold green]🚢 Saleha Autonomous Cloud Deployer[/]', border_style='green'))
    for asset in plan.assets:
        console.print(f'[bold yellow]📄 {asset.relative_path}[/] - [dim]{asset.description}[/]')
    if auto_apply:
        written = _cmds.cloud_deployer.apply_plan(plan, target_dir=target_dir)
        console.print(f'\n[bold green]✅ Applied {len(written)} deployment files to workspace:[/]')
        for w in written:
            console.print(f'  • [cyan]{w}[/]')
    else:
        console.print("\n[dim]Run 'saleha ship --apply' to write these deployment files directly to disk.[/]\n")

@cli.command(name='changelog')
@click.option('--version', default='1.5.0', help='Release version number')
@click.option('--write', 'write_file', is_flag=True, help='Write directly to CHANGELOG.md')
def changelog_cmd(version, write_file):
    """
    Generate SemVer changelog and GitHub release notes from conventional commits.
    
    Example: saleha changelog --version 1.5.0 --write
    """
    from saleha.core.changelog_generator import changelog_generator
    notes = changelog_generator.generate_release_notes(version=version)
    console.print(Markdown(notes))
    if write_file:
        saved_p = changelog_generator.update_changelog_file(version=version)
        console.print(f'\n[bold green]✅ Updated changelog at:[/] [cyan]{saved_p}[/]\n')

@cli.command(name='snapshot')
@click.argument('paths', nargs=-1)
@click.option('--label', default='manual_snapshot', help='Label for the snapshot')
def snapshot_cmd(paths: tuple, label: str) -> None:
    """
    Create an atomic point-in-time workspace snapshot.

    Example: saleha snapshot pyproject.toml saleha/core/
    """
    from saleha.core.time_machine import time_machine
    target_paths = list(paths) or ['pyproject.toml']
    snap = time_machine.create_snapshot(target_paths, label=label)
    console.print(
        f"[bold green]Snapshot created:[/bold green] ID='{snap.snapshot_id}', "
        f"{snap.file_count} file(s) captured -> {time_machine.store_dir}"
    )

@cli.command(name='rollback')
@click.option('--snapshot-id', default=None, help='Snapshot ID to rollback to')
def rollback_cmd(snapshot_id: Optional[str]) -> None:
    """
    Instant 1-click rollback to a previous workspace snapshot.

    Example: saleha rollback
    """
    from saleha.core.time_machine import time_machine
    success, msg = time_machine.rollback(snapshot_id)
    color = 'green' if success else 'red'
    console.print(f'[bold {color}]{msg}[/bold {color}]')

@cli.command('release-check')
def release_check_cli_cmd():
    """Validate project manifests and release readiness across all workspaces."""
    from saleha.tools.release_manager import release_manager
    console.print('[bold cyan]📦 Checking Saleha Ecosystem Release Readiness...[/bold cyan]\n')
    report = release_manager.check_release_readiness()
    table = Table(title=f'Release Pre-Flight Report (v{report.version})', border_style='green' if report.success else 'red')
    table.add_column('Manifest Component', style='white')
    table.add_column('Status', style='bold')
    table.add_row('pyproject.toml (Python Engine)', '[green]PASS[/]' if report.pyproject_valid else '[red]FAIL[/]')
    table.add_row('Cargo.toml (Tauri Native Desktop)', '[green]PASS[/]' if report.cargo_valid else '[red]FAIL[/]')
    table.add_row('package.json (@saleha/ui)', '[green]PASS[/]' if report.packages_valid else '[red]FAIL[/]')
    table.add_row('Core CLI Entrypoint', '[green]PASS[/]')
    console.print(table)
    if report.success:
        console.print(f'\n[bold green]✅ All {report.total_checks} workspace checks passed ({report.duration_ms}ms). Ready for release build![/bold green]\n')
    else:
        console.print(f"\n[bold red]❌ Release checks failed with issues: {', '.join(report.issues)}[/bold red]\n")

