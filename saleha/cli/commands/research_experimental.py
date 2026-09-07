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

@cli.command(name='jarvis')
@click.pass_context
def jarvis_cmd(ctx):
    """Alias for 'saleha voice' assistant mode."""
    ctx.forward(voice_cmd)

@cli.command(name='cognitive')
@click.argument('path', required=True)
def cognitive_cmd(path: str):
    """
    4D Cognitive State & Ethics Analysis (Temporal, Spatial, Ethical, Reasoning).
    
    Example: saleha cognitive saleha/core/security_scanner.py
    """
    from saleha.core.cognitive_engine import CognitiveEngine
    if not os.path.exists(path):
        console.print(f"[bold red]❌ Error: Path '{path}' not found.[/bold red]")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    engine = CognitiveEngine()
    rep = engine.evaluate_code(code, filename=os.path.basename(path))
    console.print(Panel(f'[bold magenta]🧭 4D Cognitive State Report: {path}[/bold magenta]\n[bold green]{rep.summary}[/bold green]', border_style='magenta'))
    table = Table(title='Cognitive Dimensions Breakdown', border_style='magenta')
    table.add_column('Dimension', style='bold')
    table.add_column('Score', style='cyan')
    table.add_column('Rating', style='yellow')
    table.add_column('Key Observation', style='white')
    for d in [rep.temporal, rep.spatial, rep.ethical, rep.reasoning]:
        obs = d.observations[0] if d.observations else 'Optimal'
        table.add_row(d.dimension, f'{d.score}/100', d.rating, obs[:60])
    console.print(table)

@cli.command(name='ledger')
def ledger_cmd():
    """
    Inspect the Double-Entry Token Economics & ROI Ledger.
    
    Example: saleha ledger
    """
    from saleha.core.token_ledger import token_ledger
    summary = token_ledger.get_summary()
    console.print(Panel('[bold green]💰 Saleha Double-Entry Token & Compute ROI Ledger[/bold green]', border_style='green'))
    table = Table(border_style='green')
    table.add_column('Metric', style='bold white')
    table.add_column('Value', style='bold cyan')
    table.add_row('Total Transactions', str(summary['total_transactions']))
    table.add_row('Total Tokens Consumed', f"{summary['total_tokens_consumed']:,}")
    table.add_row('Total Tokens Saved (Memory Credits)', f"{summary['total_tokens_saved']:,}")
    table.add_row('Estimated API Spend', f"${summary['estimated_spend_usd']}")
    table.add_row('Estimated Value Saved', f"${summary['estimated_savings_usd']}")
    table.add_row('Net Token ROI', f"{summary['token_roi_percent']}%")
    console.print(table)

@cli.command(name='optimize-prompts')
@click.option('--role', default='CoderAgent', help='Agent role to optimize')
def optimize_prompts_cmd(role: str):
    """
    Auto-Curriculum & Prompt Self-Optimizer (DSPy/OPRO style).
    
    Example: saleha optimize-prompts --role CoderAgent
    """
    from saleha.core.prompt_optimizer import prompt_optimizer, recent_real_errors
    console.print(Panel(f'[bold magenta]🧬 Saleha Auto-Curriculum Prompt Optimizer: {role}[/bold magenta]', border_style='magenta'))
    # This used to pass a hardcoded failure list -- literally
    # ['IndexError in test suite'] -- so it "self-optimized" against an error
    # that had never happened, while real failures sat unused in TaskHistory.
    errors = recent_real_errors()
    if not errors:
        console.print('[yellow]No recorded failures to learn from yet.[/] '
                      'Run some tasks first; this optimizer only learns from '
                      'real errors, and inventing one would teach it nothing.')
        return
    rec = prompt_optimizer.optimize_prompt(role, 'You are a senior AI software engineer.', errors)
    console.print(f'[dim]Learned from {rec.errors_seen} real failure(s) in task history.[/dim]')
    console.print(f'[bold green]Optimized Prompt Iteration #{rec.iteration}:[/bold green]\n{rec.optimized_prompt}')
    if rec.unmatched_errors:
        console.print(f'[yellow]{len(rec.unmatched_errors)} failure(s) had no matching rule '
                      f'and were NOT learned from:[/]')
        for err in rec.unmatched_errors[:5]:
            console.print(f'  [dim]- {err[:100]}[/dim]')

@cli.command(name='design-model')
@click.argument('name', default='SalehaTransformer')
def design_model_cmd(name: str):
    """
    Synthesize custom PyTorch / ONNX Neural Transformer architectures.
    
    Example: saleha design-model SalehaLLM
    """
    from saleha.core.neural_designer import neural_designer, NeuralArchitectureSpec
    spec = NeuralArchitectureSpec(model_name=name)
    rep = neural_designer.design_transformer(spec)
    console.print(Panel(f'[bold cyan]🧠 Neural Architecture Designer: {name}[/bold cyan]\n{rep.summary}', border_style='cyan'))

@cli.command(name='generate-app')
@click.argument('name', default='SalehaApp')
@click.option('--desc', default='Dynamic HTMX Application', help='App description')
@click.option('--out', default='apps/generated_app', help='Output directory')
def generate_app_cmd(name: str, desc: str, out: str):
    """
    Synthesize Zero-JS HTMX + Python dynamic web application.
    
    Example: saleha generate-app MyDashboard
    """
    from saleha.core.htmx_generator import htmx_generator
    pkg = htmx_generator.generate_app(app_name=name, description=desc)
    htmx_generator.write_to_disk(out, pkg)
    console.print(f"[bold green]✅ HTMX App '{name}' generated in '{out}'![/bold green]")

@cli.command(name='quantum-sim')
@click.option('--gates', default='H,X,H', help='Comma-separated quantum gates (e.g. H,X,H)')
def quantum_sim_cmd(gates: str):
    """
    Quantum Logic & M-Theory Tensor Simulator.
    
    Example: saleha quantum-sim --gates H,X,H
    """
    from saleha.core.quantum_compiler import quantum_compiler
    gate_list = [g.strip() for g in gates.split(',') if g.strip()]
    res = quantum_compiler.simulate_circuit(gate_list)
    console.print(Panel(f'[bold magenta]⚛️ Quantum State Reality Simulation[/bold magenta]\n{res.summary}', border_style='magenta'))

@cli.command(name='search-code')
@click.argument('query', required=True)
@click.option('--path', default='saleha', help='Path to search (default: saleha)')
def search_code_cmd(query: str, path: str):
    """
    Sub-millisecond Zero-Latency Local Code Search.
    
    Example: saleha search-code "solve_issue"
    """
    from saleha.core.fast_search import fast_search_engine
    fast_search_engine.index_directory(path)
    matches = fast_search_engine.search(query, limit=10)
    console.print(Panel(f"[bold cyan]🔍 Fast Code Search for '{query}' ({len(matches)} matches)[/bold cyan]", border_style='cyan'))
    for m in matches:
        console.print(f'- [bold white]{m.file_path}:{m.line_number}[/bold white] ([italic yellow]{m.symbol_type}[/italic yellow]): `{m.snippet}`')

@cli.command(name='causal-eval')
@click.option('--target', default='latency_ms', help='Target outcome metric (e.g. latency_ms, defect_rate, throughput_rps)')
def causal_eval_cmd(target: str):
    """
    Query a small structural causal model of software-engineering variables.

    The graph is hand-written (six variables, hand-assigned edge weights) and
    is NOT derived from your codebase. This evaluates that fixed graph.

    Example: saleha causal-eval --target latency_ms
    """
    from saleha.core.causal_world_model import causal_world_model
    rep = causal_world_model.simulate_l2_intervention({'use_async_io': True, 'has_memory_cache': True}, target)
    console.print(Panel(f'[bold cyan]Causal model ({rep.inquiry_level})[/bold cyan]\n{rep.reasoning}',
                        border_style='cyan'))
    console.print(f'  [dim]association-only answer: {rep.association_outcome} | '
                  f'differs after graph surgery: {rep.differs_from_association}[/]')
    console.print('  [dim]- The graph is hand-written, not learned from this '
                  'codebase; edge weights are judgement calls.[/]')

@cli.command(name='explain-code')
@click.argument('path', required=True)
def explain_code_cmd(path: str):
    """
    Explain the structure of a Python file: error handling, type contracts,
    control flow, resource management, and per-function complexity.

    This is an AST-based structural analysis of the source. It does not
    inspect any model's internals -- no activations, no saliency.

    Example: saleha explain-code saleha/core/security_scanner.py
    """
    from saleha.core.mech_interp import code_structure_engine
    if not os.path.exists(path):
        console.print(f"[bold red]❌ Error: Path '{path}' not found.[/bold red]")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()
    rep = code_structure_engine.explain_code(code, filename=os.path.basename(path))

    if not rep.parsed:
        console.print(Panel(
            f'[bold yellow]⚠ Could not parse {path}[/bold yellow]\n{rep.summary}',
            border_style='yellow'))
        return

    console.print(Panel(f'[bold cyan]🔬 Code structure: {path}[/bold cyan]\n{rep.summary}',
                        border_style='cyan'))

    if rep.functions:
        table = Table(title='Functions by branching complexity', show_lines=False)
        table.add_column('Function', style='cyan')
        table.add_column('Line', justify='right')
        table.add_column('Cx', justify='right')
        table.add_column('Args', justify='right')
        table.add_column('Doc', justify='center')
        table.add_column('Typed', justify='center')
        for fn in sorted(rep.functions, key=lambda f: f.complexity, reverse=True)[:15]:
            # Cyclomatic complexity over 10 is the usual "worth a look" line.
            style = 'red' if fn.complexity > 10 else ''
            table.add_row(
                f'{"async " if fn.is_async else ""}{fn.qualname}',
                str(fn.line_number), str(fn.complexity), str(fn.arg_count),
                '✓' if fn.has_docstring else '·',
                '✓' if fn.is_annotated else '·',
                style=style)
        console.print(table)

    bare = [a for a in rep.attributions if 'Bare `except:`' in a.rationale]
    if bare:
        console.print(f'[yellow]⚠ {len(bare)} bare except clause(s): '
                      f'lines {", ".join(str(a.line_number) for a in bare[:10])}[/]')

