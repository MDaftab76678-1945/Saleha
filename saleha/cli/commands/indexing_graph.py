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
@click.option('--parallel/--no-parallel', default=True, help='Execute independent task batches in parallel')
@click.option('--workers', '-w', default=4, type=int, help='Maximum parallel worker threads')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def dag(goal, parallel, workers, model, as_json):
    """Execute a complex engineering goal using a parallel Directed Acyclic Graph (DAG) of agents."""
    task_dag = _cmds.TaskDAG.build_default_dag_for_goal(goal=goal, model=model)
    if as_json:
        with redirect_stdout(io.StringIO()):
            res = task_dag.execute_parallel(max_workers=workers if parallel else 1)
        payload = {'success': res.success, 'goal': res.goal, 'total_tasks': res.total_tasks, 'completed_tasks': res.completed_tasks, 'failed_tasks': res.failed_tasks, 'total_time': res.total_time, 'mermaid_graph': res.mermaid_graph, 'tasks': {node.id: {'title': node.title, 'role_profile': node.role_profile, 'status': node.status, 'duration': node.duration, 'result_preview': node.result[:150] if node.result else '', 'error': node.error} for node in res.nodes.values()}}
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not res.success:
            raise click.exceptions.Exit(1)
        return
    console.print(Panel.fit(f"[bold cyan]🎯 DAG Goal:[/] {goal}\n[bold cyan]⚡ Mode:[/] {('Parallel Execution (' + str(workers) + ' threads)' if parallel else 'Sequential')}\n[bold cyan]📊 Total Nodes:[/] {len(task_dag.nodes)}", title='[bold green]⚡ Parallel Multi-Agent Task Graph (DAG)[/]', border_style='green'))
    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
        progress.add_task('[cyan]Executing DAG nodes in topological order...', total=None)
        res = task_dag.execute_parallel(max_workers=workers if parallel else 1)
    table = Table(title='📊 DAG Node Execution Status', show_header=True, header_style='bold magenta')
    table.add_column('Node ID', style='cyan')
    table.add_column('Task Title', style='white')
    table.add_column('Agent Profile', style='yellow')
    table.add_column('Duration', justify='right', style='dim')
    table.add_column('Status', justify='center')
    for node in res.nodes.values():
        status = '[green]✅ COMPLETED[/]' if node.status == 'COMPLETED' else '[red]❌ FAILED[/]'
        table.add_row(node.id, node.title, node.role_profile, f'{node.duration:.2f}s', status)
    console.print(table)
    console.print(f'\n[bold green]⏱️ Total DAG Execution Time:[/] {res.total_time:.2f}s')

@cli.command(name='graph')
@click.option('--output', default='docs/architecture_graph.html', help='Path to output HTML file')
@click.option('--dir', 'target_dir', default='.', help='Workspace root directory to map')
def graph_cmd(output, target_dir):
    """
    Generate live interactive 2D/3D force-directed architecture visualizer HTML.
    
    Example: saleha graph --output docs/architecture_graph.html
    """
    from saleha.core.graph_visualizer import ArchitectureGraphVisualizer
    console.print(f'[bold cyan]🗺️ Generating interactive architecture graph visualizer for:[/] [yellow]{target_dir}[/]')
    vis = ArchitectureGraphVisualizer(root_dir=target_dir)
    out_p = vis.render_html(output_path=output)
    console.print(f'\n[bold green]✅ Interactive Architecture Graph generated:[/] [cyan]{out_p}[/]')
    console.print('[dim]Open this file in your browser to inspect nodes and dependencies.[/]\n')

@cli.command(name='callers')
@click.argument('symbol')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def callers_cmd(symbol, as_json):
    """Find all code callers referencing a specific function, class, or method."""
    from saleha.core.dependency_graph import dependency_graph
    if not dependency_graph.files_indexed:
        dependency_graph.build_graph()
    callers = dependency_graph.find_callers(symbol)
    if as_json:
        payload = [{'symbol': c.symbol_called, 'file': c.caller_file, 'line': c.caller_line, 'context': c.caller_context} for c in callers]
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    if not callers:
        console.print(f"[yellow]No callers found for symbol '{symbol}'.[/]")
        return
    from rich.table import Table
    table = Table(title=f"🌲 Callers of '{symbol}'", border_style='cyan')
    table.add_column('Caller File', style='bold cyan')
    table.add_column('Line', style='yellow')
    table.add_column('Context', style='green')
    for c in callers:
        table.add_row(c.caller_file, str(c.caller_line), c.caller_context)
    console.print(table)

@cli.command(name='rag')
@click.argument('question')
@click.option('--path', '-p', default='.', help='Codebase path to index')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def rag_cmd(question, path, as_json):
    """Natural language architectural Q&A fused with AST Dependency Graph."""
    from saleha.core.graph_rag import graph_rag
    ans = graph_rag.query(question=question, root_dir=path)
    if as_json:
        click.echo(json.dumps({'question': ans.question, 'answer': ans.answer, 'relevant_files': ans.relevant_files, 'key_symbols': ans.key_symbols, 'call_hierarchy': ans.call_hierarchy}, ensure_ascii=True))
        return
    console.print(Panel(f"[bold cyan]Question:[/] {ans.question}\n[bold cyan]Relevant Files:[/] {', '.join(ans.relevant_files[:5]) or 'All'}\n[bold cyan]Key Symbols:[/] {', '.join(ans.key_symbols[:5]) or 'General'}", title='[bold green]🧠 Saleha Graph RAG Codebase Q&A[/]', border_style='green'))
    console.print(Markdown(ans.answer))

@cli.command(name='fix')
@click.argument('command_or_file', default='pytest')
@click.option('--retries', default=3, help='Max healing attempts')
@click.option('--no-commit', is_flag=True, help='Do not auto-commit verified fix')
def fix_cmd(command_or_file, retries, no_commit):
    """
    Autonomous Self-Healing Loop: Runs a failing command/test, localizes fault, patches and verifies.
    
    Example: saleha fix "pytest saleha/tests/test_foo.py"
    """
    from saleha.core.self_healer import self_healer
    console.print(f'[bold cyan]🩹 Running Autonomous Self-Healer on:[/] [yellow]{command_or_file}[/]')
    result = self_healer.auto_heal(command_or_file, max_retries=retries, auto_commit=not no_commit)
    if result.success:
        if result.attempts_made == 0:
            console.print('[bold green]✅ Command is already passing! Zero errors detected.[/]')
        else:
            console.print(f'[bold green]🎉 Healed successfully in {result.attempts_made} attempt(s)![/]')
            if result.commit_hash:
                console.print(f'[cyan]📦 Git Commit:[/] [yellow]{result.commit_hash}[/]')
    else:
        console.print(f'[bold red]❌ Healing failed:[/] {result.error}')
        if result.diagnostics:
            console.print(f'[dim]Faulting Location: {result.diagnostics.faulting_file}:{result.diagnostics.faulting_line}[/]')

@cli.command(name='search')
@click.argument('query')
@click.option('--limit', default=10, help='Max results to display')
@click.option('--semantic/--lexical', default=True, help='Enable hybrid BM25 + Vector cosine similarity')
@click.option('--json', 'as_json', is_flag=True, help='Output JSON format')
def search_cmd(query, limit, semantic, as_json):
    """
    Hybrid BM25 + Vector Semantic Code Search across codebase symbols and syntax trees.
    
    Example: saleha search "memory compact history" --semantic
    """
    from saleha.core.semantic_search import semantic_search
    results = semantic_search.search(query, top_k=limit, semantic=semantic)
    if as_json:
        click.echo(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2))
        return
    table = Table(title=f"🔎 Codebase Search: '{query}' ({('Hybrid Semantic' if semantic else 'Lexical BM25')})", show_header=True, header_style='bold magenta', expand=True)
    table.add_column('Score', width=8, style='bold green')
    table.add_column('Location', style='bold cyan', width=30)
    table.add_column('Type', width=12, style='yellow')
    table.add_column('Snippet / Symbol', style='white')
    for r in results:
        table.add_row(f'{r.score:.3f}', f'{r.file_path}:{r.line_number}', r.symbol_type, r.snippet)
    console.print(table)
    if not results:
        console.print('[dim]No matching symbols or comments found.[/]\n')

@cli.command(name='learn')
@click.argument('skill_goal')
@click.option('--name', default=None, help='Custom skill identifier name')
def learn_cmd(skill_goal, name):
    """
    Synthesize and distill an engineering task pattern into a permanent reusable skill.
    
    Example: saleha learn "optimize postgres connection pool and vacuum"
    """
    from saleha.core.skill_synthesizer import skill_synthesizer
    console.print(f'[bold cyan]🧠 Distilling continuous learning skill for:[/] [yellow]{skill_goal}[/]')
    skill = skill_synthesizer.distill_from_execution(task_goal=skill_goal, execution_trace=f'Task pattern: {skill_goal}', skill_name=name)
    saved_path = skill_synthesizer.save_skill(skill)
    console.print(f'\n[bold green]✅ Synthesized permanent skill:[/] [cyan]{skill.name}[/]')
    console.print(f'[dim]Saved to: {saved_path}[/]\n')

@cli.command(name='budget')
@click.option('--history', is_flag=True, help='Show recent invocation history')
def budget_cmd(history):
    """
    Token Economics & Cumulative Cloud API Cost Savings Analytics.
    
    Example: saleha budget
    """
    from saleha.core.token_analytics import token_analytics
    summary = token_analytics.get_summary()
    table = Table(title='💰 Token Economics & Cloud Cost Savings', show_header=True, header_style='bold green', expand=True)
    table.add_column('Metric', style='bold white')
    table.add_column('Value', style='cyan')
    table.add_row('Total Invocations', str(summary['total_invocations']))
    table.add_row('Total Tokens (In + Out)', f"{summary['total_tokens']:,}")
    table.add_row('Prompt Tokens', f"{summary['total_prompt_tokens']:,}")
    table.add_row('Completion Tokens', f"{summary['total_completion_tokens']:,}")
    table.add_row('Reasoning (<think>) Tokens', f"{summary['total_reasoning_tokens']:,}")
    table.add_row('Average Generation Speed', f"{summary['average_speed_tps']} tokens/sec")
    table.add_row('Claude 3.5 Sonnet Equivalent Saved', f"[bold green]{summary['claude_equivalent_saved']}[/]")
    table.add_row('GPT-4o Equivalent Saved', f"[bold green]{summary['gpt4o_equivalent_saved']}[/]")
    console.print(table)

@cli.command(name='diff-preview')
@click.argument('file_path')
@click.argument('new_file_path')
def diff_preview_cmd(file_path, new_file_path):
    """
    Preview Surgical Unified Diff with AST Blast Radius & Risk Score.
    
    Example: saleha diff-preview old.py new.py
    """
    from saleha.core.diff_engine import diff_engine
    from saleha.core.change_impact import change_impact
    with open(file_path, 'r', encoding='utf-8') as f:
        old_code = f.read()
    with open(new_file_path, 'r', encoding='utf-8') as f:
        new_code = f.read()
    diff = diff_engine.compute_diff(file_path, old_code, new_code)
    impact = change_impact.analyze(old_code, new_code, file_path)
    console.print(diff_engine.format_rich_preview(diff))
    console.print(f'\n[bold magenta]💥 AST Impact Analysis:[/] {impact.summary}')
    console.print(f"  Blast Radius: [bold {('red' if impact.blast_radius > 50 else 'green')}]{impact.blast_radius}/100[/] ({impact.risk_level.upper()} RISK)")

