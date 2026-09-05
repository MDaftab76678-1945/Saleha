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
@click.option('--output-dir', '-o', type=click.Path(file_okay=False), help='Directory to export all artifacts (PRD, Design, Code, Tests, Security)')
@click.option('--debate', is_flag=True, help='Enable multi-agent debate and consensus refinement')
@click.option('--max-attempts', default=3, type=click.IntRange(1, 10), help='Maximum self-healing attempts')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def team(goal, model, output_dir, debate, max_attempts, as_json):
    """
    Run multi-agent collaborative swarm pipeline:
    PM (PRD) -> Architect (LLD) -> SDE (Code) -> Security (Audit) -> QA (Tests) -> Verifier (Execution)
    
    Example: saleha team "Build an in-memory caching system with TTL"
    Example with debate: saleha team "Build a distributed lock manager" --debate --output-dir ./dist_lock
    """
    orchestrator = _cmds.TeamOrchestrator(model=model, max_healing_attempts=max_attempts)
    if as_json:
        with redirect_stdout(io.StringIO()):
            result = orchestrator.run_team_workflow(goal=goal, output_dir=output_dir, debate=debate)
    else:
        out_info = f'\n[bold cyan]📁 Output Dir:[/] {output_dir}' if output_dir else ''
        debate_info = '\n[bold yellow]🤝 Mode:[/] Multi-Agent Deliberation & Debate Enabled' if debate else ''
        console.print(Panel.fit(f'[bold cyan]🎯 Swarm Goal:[/] {goal}\n[bold cyan]🤖 Model:[/] {model}{out_info}{debate_info}\n[bold cyan]👥 Swarm Team:[/] ProductManager ➔ Architect ➔ SDE ➔ Security ➔ QA ➔ Verifier', title='[bold green]Saleha Multi-Agent Swarm[/]', border_style='green'))
        with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
            progress.add_task('[cyan]Collaborating across team...', total=None)
            result = orchestrator.run_team_workflow(goal=goal, output_dir=output_dir, debate=debate)
    if as_json:
        payload = {'success': result.success, 'goal': result.goal, 'stages_completed': result.stages_completed, 'prd': result.prd, 'design': result.design, 'code': result.code, 'security_report': result.security_report, 'test_code': result.test_code, 'execution_output': result.execution_output, 'output_dir': result.output_dir, 'attempts': result.attempts, 'log': result.log}
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    console.print()
    if result.success:
        console.print(Panel(f'[bold green]✅ TEAM SWARM SUCCESS[/] -- Completed all {len(result.stages_completed)} stages', border_style='green'))
    else:
        console.print(Panel('[bold yellow]⚠️ Swarm Finished with Warnings/Failures[/]', border_style='yellow'))
    table = Table(title='👥 Swarm Stage Breakdown', show_header=True, header_style='bold magenta')
    table.add_column('Stage', style='cyan')
    table.add_column('Agent Role', style='green')
    table.add_column('Artifact Produced', style='yellow')
    stage_map = [('1. Requirements', 'Product Manager', 'PRD & User Stories'), ('2. Architecture', 'Software Designer', 'LLD & Domain Contracts'), ('3. Implementation', 'Senior SDE', 'Production Python Code'), ('4. Security', 'Security Engineer', 'Vulnerability & SAST Audit'), ('5. QA & Verification', 'Test Architect', 'Test Suite & Execution Verification')]
    for stage_name, role_name, artifact in stage_map:
        table.add_row(stage_name, role_name, artifact)
    console.print(table)
    if result.code:
        console.print('\n[bold cyan]💻 Production Code (Preview):[/]')
        syntax = Syntax(result.code[:600] + ('\n# ... (continued)' if len(result.code) > 600 else ''), 'python', theme='monokai', line_numbers=True)
        console.print(syntax)
    if result.output_dir:
        console.print(f'\n[bold green]📁 Full Artifact Package Exported To:[/] {result.output_dir}')

@cli.command(name='debate')
@click.argument('topic')
@click.option('--rounds', '-r', default=2, help='Number of dialectic debate rounds')
def debate_cmd(topic: str, rounds: int):
    """Execute game-theoretic multi-agent council debate (Advocate, Devil's Advocate, Security, FinOps, Arbiter)."""
    from saleha.core.debate_consensus_orchestrator import debate_orchestrator
    console.print(f'[bold purple]⚖️ Conducting Multi-Agent Architectural Debate on:[/] [white]{topic}[/]')
    verdict = debate_orchestrator.conduct_architectural_debate(topic=topic, num_rounds=rounds)
    for rnd in verdict.rounds:
        console.print(f'\n[bold yellow]--- Round {rnd.round_number} ---[/]')
        console.print(f'[green]🟢 Advocate:[/] {rnd.advocate_argument}')
        console.print(f"[red]🔴 Devil's Advocate:[/] {rnd.skeptic_rebuttal}")
        console.print(f'[cyan]🛡️ Security Red-Team:[/] {rnd.security_critique}')
        console.print(f'[magenta]💰 FinOps Auditor:[/] {rnd.finops_impact}')
    console.print(f'\n[bold green]🏆 Consensus Decision (Elo Confidence: {verdict.elo_confidence_score * 100:.1f}%):[/]')
    console.print(Panel(verdict.adr_markdown[:400] + '\n  ...', title='Synthesized Architecture Decision Record (ADR)', border_style='green'))

@cli.command(name='council')
@click.argument('problem')
def council_cmd(problem):
    """
    Assemble Multi-Agent Architectural Council to debate & synthesize optimal solution.
    
    Example: saleha council "Design a high-throughput distributed caching layer"
    """
    from saleha.core.agent_council import agent_council
    console.print(f'[bold cyan]👥 Assembling Multi-Agent Architectural Council for:[/] [yellow]{problem}[/]\n')
    res = agent_council.debate_and_synthesize(problem)
    for p in res.proposals:
        console.print(f'[bold magenta]{p.persona_name}[/] — [italic]{p.perspective}[/] (Score: {p.overall_score}/100)')
        for arg in p.key_arguments:
            console.print(f'  • {arg}')
        console.print()
    console.print(f'[bold green]🏆 Consensus Winner:[/] {res.winning_persona} (Consensus Score: {res.total_consensus_score}/100)')
    console.print(f'\n[bold cyan]Synthesized Consensus Code:[/]\n{res.consensus_code}')

@cli.command(name='resolve-conflicts')
@click.argument('path', default='.')
@click.option('--auto-stage', is_flag=True, help='Automatically git add resolved files')
def resolve_conflicts_cmd(path, auto_stage):
    """
    Autonomously detect and resolve Git merge conflicts with AST semantic analysis.
    
    Example: saleha resolve-conflicts . --auto-stage
    """
    from saleha.core.conflict_resolver import conflict_resolver
    console.print(f'[bold cyan]🔀 Scanning for Git merge conflicts in:[/] [yellow]{os.path.abspath(path)}[/]')
    files_to_check = []
    if os.path.isfile(path):
        files_to_check.append(path)
    else:
        for root, _, files in os.walk(path):
            if any((p.startswith('.') or p == 'node_modules' for p in root.split(os.sep))):
                continue
            for f in files:
                if f.endswith(('.py', '.js', '.ts', '.json', '.md', '.txt', '.go', '.rs')):
                    files_to_check.append(os.path.join(root, f))
    resolved_count = 0
    for fpath in files_to_check:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        if conflict_resolver.has_conflicts(content):
            res = conflict_resolver.resolve_file(fpath, auto_save=True)
            if res.status == 'RESOLVED':
                console.print(f'[bold green]✅ Resolved Conflicts in:[/] {fpath} ({res.summary})')
                resolved_count += 1
                if auto_stage:
                    subprocess.run(['git', 'add', fpath])
            else:
                console.print(f'[bold yellow]⚠️ Manual Review Needed:[/] {fpath} ({res.summary})')
    if resolved_count == 0:
        console.print('[green]No merge conflicts found in workspace.[/]')
    else:
        console.print(f'\n[bold green]🎉 Successfully resolved {resolved_count} conflicted file(s)![/]')

@cli.command(name='recursive')
@click.argument('goal', required=True)
@click.option('--model', default='auto', help='Model to use for multi-path reasoning')
def recursive_cmd(goal: str, model: str):
    """
    7-Node Recursive Intelligence Network & Multi-Path Problem Solver.
    
    Example: saleha recursive "Find longest palindromic substring in O(n)"
    """
    from saleha.core.recursive_solver import RecursiveSolver
    console.print(Panel(f'[bold cyan]🧠 Saleha Recursive Intelligence Network[/bold cyan]\n[italic]{goal}[/italic]', border_style='cyan'))
    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), transient=True) as progress:
        progress.add_task(description='Exploring multi-path reasoning trajectories...', total=None)
        solver = RecursiveSolver(model=model)
        result = solver.solve(goal)
    table = Table(title='Reasoning Trajectories Explored', border_style='cyan')
    table.add_column('Path ID', style='bold')
    table.add_column('Strategy', style='white')
    table.add_column('Complexity (T / S)', style='green')
    table.add_column('Score', style='yellow')
    for p in result.paths_explored:
        winner = ' 🏆 (Winner)' if p.path_id == result.winning_path_id else ''
        table.add_row(p.path_id, f'{p.name}{winner}', f'{p.complexity_time} / {p.complexity_space}', f'{p.score}/10')
    console.print(table)
    if result.success:
        console.print('\n[bold green]✅ Optimal Solution Verified & Synthesized:[/bold green]')
        console.print(Syntax(result.final_code, 'python', theme='monokai', line_numbers=True))
    else:
        console.print(f'\n[bold red]⚠️ Solution Completed with Warnings:[/bold red]\n{result.log}')

@cli.command(name='consensus')
def consensus_cmd():
    """
    Inspect the Swarm PBFT Byzantine Fault Tolerance Consensus status.
    
    Example: saleha consensus
    """
    from saleha.core.swarm_consensus import swarm_consensus
    console.print(Panel('[bold cyan]🛡️ Saleha Swarm PBFT Consensus Engine[/bold cyan]', border_style='cyan'))
    table = Table(border_style='cyan')
    table.add_column('Property', style='bold white')
    table.add_column('Value', style='bold green')
    table.add_row('Registered Validators', ', '.join(sorted(swarm_consensus.validators)))
    table.add_row('Fault Tolerance Rule', '2f + 1 Quorum (PBFT 3-Phase)')
    table.add_row('Total Proposals Processed', str(len(swarm_consensus.proposals)))
    console.print(table)

@cli.command(name='multirepo')
@click.argument('goal')
@click.option('--repos', '-r', required=True, help="Comma-separated repository names (e.g. 'api-gateway,web-client,auth-service')")
def multirepo_cmd(goal: str, repos: str):
    """Coordinate cross-repository atomic refactorings, breaking contract sync, and correlated PRs."""
    from saleha.core.multirepo_orchestrator import multirepo_orchestrator
    repo_list = [r.strip() for r in repos.split(',') if r.strip()]
    console.print(f'[bold magenta]🔗 Coordinating Multi-Repo Migration across {len(repo_list)} repositories...[/]')
    plan = multirepo_orchestrator.plan_multirepo_sync(goal=goal, repos=repo_list)
    table = Table(title=f'Multi-Repo Transformation Matrix: {goal}', border_style='magenta')
    table.add_column('Repository', style='bold cyan')
    table.add_column('Branch', style='yellow')
    table.add_column('Files Changed', style='green')
    table.add_column('PR Title', style='white')
    for repo, trans in plan.transforms.items():
        table.add_row(trans.repo_name, trans.branch_name, ', '.join(trans.files_changed), trans.pr_title)
    console.print(table)
    console.print(f"[bold green]✅ Atomic execution sequence mapped:[/] {' -> '.join(plan.migration_order)}")

@cli.command(name='tot-solve')
@click.argument('goal')
@click.option('--code', '-c', required=True, help='Initial code string or file path')
@click.option('--tests', '-t', required=True, help='Verification test assertions code string or file path')
def tot_solve_cmd(goal: str, code: str, tests: str):
    """Solve tricky coding bugs with Tree-of-Thoughts (ToT) state-space search and backtracking."""
    from saleha.core.tot_orchestrator import tot_orchestrator
    code_content = Path(code).read_text(encoding='utf-8') if os.path.exists(code) else code.replace('\\n', '\n')
    tests_content = Path(tests).read_text(encoding='utf-8') if os.path.exists(tests) else tests.replace('\\n', '\n')
    console.print(f'[bold cyan]🌲 Starting Tree-of-Thoughts (ToT) Search for:[/] [white]{goal}[/]')
    res = tot_orchestrator.solve_task_with_tot(goal=goal, initial_code=code_content, test_suite=tests_content)
    for line in res.execution_log:
        console.print(f'[dim]{line}[/dim]')
    if res.success:
        console.print(f'[bold green]✨ ToT Solution Found! Total nodes explored: {res.total_nodes_explored} (Pruned: {res.pruned_nodes})[/bold green]')
        console.print(Panel(res.final_code, title='Winning Code Patch', border_style='green'))
    else:
        console.print(f'[bold yellow]⚠️ Best-effort candidate reached with score. Nodes: {res.total_nodes_explored}[/bold yellow]')

@cli.command('swarm')
@click.argument('goal', default='Build a robust distributed worker pool')
def swarm_cli_cmd(goal: str):
    """Execute dynamic multi-agent DAG swarm pipeline with real-time ASCII visualization."""
    from saleha.core.swarm_pipeline_engine import swarm_engine
    from saleha.cli.swarm_visualizer import visualizer
    visualizer.render_header(goal)
    stage_counter = [0]
    total_stages = 6

    def on_stage(stage):
        if stage.status == 'success':
            stage_counter[0] += 1
            visualizer.render_stage_update(stage, stage_counter[0], total_stages)
    res = swarm_engine.execute_swarm(goal, callback=on_stage)
    visualizer.render_execution_summary(res)

