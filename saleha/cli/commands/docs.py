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

@cli.command(name='doc')
@click.argument('package')
@click.argument('symbol', required=False, default=None)
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def doc_cmd(package, symbol, as_json):
    """Look up verified API signatures from local offline documentation cache."""
    from saleha.core.doc_researcher import doc_researcher
    from dataclasses import asdict
    if symbol:
        sig = doc_researcher.lookup(package, symbol)
        if as_json:
            click.echo(json.dumps(asdict(sig) if sig else None, ensure_ascii=True))
            return
        if sig:
            console.print(Panel(f'[bold cyan]Package:[/] {sig.package}\n[bold cyan]Symbol:[/] {sig.symbol}\n[bold yellow]Signature:[/] `{sig.signature}`\n\n[bold green]Description:[/]\n{sig.docstring}\n\n[bold dim]Example:[/]\n{sig.example}', title=f'[bold green]📖 API Reference: {sig.package}.{sig.symbol}[/]', border_style='green'))
        else:
            console.print(f"[yellow]No documentation found for '{package}.{symbol}'.[/]")
    else:
        results = doc_researcher.search_docs(package)
        if as_json:
            click.echo(json.dumps([asdict(r) for r in results], ensure_ascii=True))
            return
        if not results:
            console.print(f"[yellow]No documentation found matching '{package}'.[/]")
            return
        from rich.table import Table
        table = Table(title=f"📖 Documentation for '{package}'", border_style='cyan')
        table.add_column('Package', style='bold cyan')
        table.add_column('Symbol', style='bold yellow')
        table.add_column('Description', style='dim')
        for r in results:
            table.add_row(r.package, r.symbol, r.docstring[:60] + '...')
        console.print(table)

@cli.command(name='autodoc')
@click.argument('path', default='.')
@click.option('--output-dir', '-o', default=None, help='Directory to export Markdown docs')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def autodoc_cmd(path, output_dir, as_json):
    """Generate Markdown API docs and Mermaid architecture diagrams from AST."""
    from saleha.core.autodoc_generator import autodoc_generator
    res = autodoc_generator.generate_docs_for_directory(root_dir=path)
    if as_json:
        click.echo(json.dumps({'total_modules': res.total_modules, 'total_classes': res.total_classes, 'total_functions': res.total_functions, 'mermaid_diagram': res.mermaid_diagram, 'markdown_docs_preview': res.markdown_docs[:300]}, ensure_ascii=True))
        return
    console.print(Panel(f'[bold cyan]Modules Scanned:[/] {res.total_modules}\n[bold cyan]Classes Documented:[/] {res.total_classes}\n[bold cyan]Functions Documented:[/] {res.total_functions}', title='[bold green]📚 Saleha Auto-Documentation Generator[/]', border_style='green'))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        doc_path = os.path.join(output_dir, 'API_REFERENCE.md')
        diag_path = os.path.join(output_dir, 'ARCHITECTURE_DIAGRAM.mermaid')
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(res.markdown_docs)
        with open(diag_path, 'w', encoding='utf-8') as f:
            f.write(res.mermaid_diagram)
        console.print(f'[bold green]💾 Exported docs to:[/] {output_dir}')

@cli.command(name='docs')
@click.option('--build', 'build_site', is_flag=True, default=True, help='Build static HTML documentation site')
@click.option('--output', default='docs/site/index.html', help='Output path for docs')
def docs_cmd(build_site, output):
    """
    Build searchable static HTML documentation portal.
    
    Example: saleha docs --output docs/site/index.html
    """
    from saleha.core.docs_generator import docs_generator
    console.print('[bold cyan]📚 Building Saleha static documentation website...[/]')
    out_p = docs_generator.build_docs_site(output_path=output)
    console.print(f'[bold green]✅ Documentation built at:[/] [cyan]{out_p}[/]\n')

@cli.command('doc-gen')
@click.argument('target_dir', default='.')
@click.option('--output', default=None, help='Output markdown filepath')
def doc_gen_cli_cmd(target_dir: str, output: Optional[str]):
    """Autonomously analyze codebase and generate architecture overview & Mermaid diagrams."""
    from saleha.agents.doc_generator import doc_generator
    console.print(f'\n[bold cyan]📚 Autonomous Doc Generator — Scanning:[/] [yellow]{target_dir}[/]\n')
    spec = doc_generator.scan_and_generate_docs(target_dir)
    console.print(f'[bold green]✨ Documentation Synthesized in {spec.generation_time_ms}ms![/bold green]')
    console.print(f'  • Modules Scanned : {len(spec.modules_found)}')
    console.print(f'  • Classes Found   : {spec.total_classes}')
    console.print(f'  • Public Functions: {spec.total_functions}\n')
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(spec.full_doc_markdown, encoding='utf-8')
        console.print(f'[bold green]💾 Architecture Document saved to:[/] [cyan]{output}[/]\n')
    else:
        console.print(Panel(spec.full_doc_markdown[:1200] + '\n...', title='[bold cyan]📐 Generated Architecture Documentation[/]', border_style='cyan'))

