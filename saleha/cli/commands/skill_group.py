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

@cli.group(name='skill')
def skill_group():
    """Manage and execute 1,000+ specialized AgentSkills."""
    pass

@skill_group.command(name='list')
@click.option('--domain', '-d', help='Filter skills by domain name (e.g., frontend_web, cloud_iac, vector_rag)')
@click.option('--limit', '-l', default=25, help='Number of skills to display')
def skill_list_cmd(domain: Optional[str], limit: int):
    """List registered skills across 25 specialized domains."""
    from saleha.core.skill_catalog import skill_catalog
    skills = skill_catalog.list_skills(domain=domain, limit=limit)
    stats = skill_catalog.get_stats()
    table = Table(title=f"🧠 Saleha AgentSkills Catalog ({stats['total_skills']} Total Skills across {stats['total_domains']} Domains)", border_style='cyan')
    table.add_column('Skill Name', style='bold cyan')
    table.add_column('Domain', style='magenta')
    table.add_column('Description', style='white')
    table.add_column('Triggers', style='yellow')
    for s in skills:
        table.add_row(s.name, s.domain, s.description[:55] + '...', ', '.join(s.trigger_keywords[:3]))
    console.print(table)
    console.print(f"[dim]Showing {len(skills)} of {stats['total_skills']} skills. Use --domain or 'saleha skill search <query>' to explore.[/dim]")

@skill_group.command(name='search')
@click.argument('query')
@click.option('--domain', '-d', help='Filter search within specific domain')
@click.option('--limit', '-l', default=10, help='Maximum search results')
def skill_search_cmd(query: str, domain: Optional[str], limit: int):
    """Sub-millisecond keyword and semantic search across 1,000+ skills."""
    from saleha.core.skill_catalog import skill_catalog
    results = skill_catalog.search_skills(query, domain=domain, limit=limit)
    if not results:
        console.print(f"[bold yellow]No skills found matching '{query}'.[/bold yellow]")
        return
    table = Table(title=f"🔍 Skill Search Results for '{query}' ({len(results)} matches)", border_style='green')
    table.add_column('Skill Name', style='bold green')
    table.add_column('Domain', style='magenta')
    table.add_column('Description', style='white')
    for s in results:
        table.add_row(s.name, s.domain, s.description)
    console.print(table)

@skill_group.command(name='info')
@click.argument('skill_name')
def skill_info_cmd(skill_name: str):
    """Display full AgentSkills specification and schema for a skill."""
    from saleha.core.skill_catalog import skill_catalog
    skill = skill_catalog.get_skill(skill_name)
    if not skill:
        console.print(f"[bold red]❌ Skill '{skill_name}' not found.[/bold red]")
        return
    console.print(Panel(skill.to_markdown(), title=f'AgentSkill: {skill.name}', border_style='cyan'))

@skill_group.command(name='run')
@click.argument('skill_name')
@click.option('--task', '-t', default='Execute standard skill routine', help='Task input description')
def skill_run_cmd(skill_name: str, task: str):
    """Execute a registered AgentSkill directly."""
    from saleha.core.skill_catalog import skill_catalog
    res = skill_catalog.execute_skill(skill_name, {'task': task})
    if res.get('success'):
        console.print(Panel(json.dumps(res, indent=2), title=f"✅ Skill '{skill_name}' Execution Output", border_style='green'))
    else:
        console.print(f"[bold red]❌ Skill execution failed: {res.get('error')}[/bold red]")

@skill_group.command(name='stats')
def skill_stats_cmd():
    """Display statistical breakdown of the 1,000+ skill catalog."""
    from saleha.core.skill_catalog import skill_catalog
    stats = skill_catalog.get_stats()
    table = Table(title=f'📊 Saleha 1,000+ AgentSkills Domain Distribution', border_style='blue')
    table.add_column('Domain Name', style='bold cyan')
    table.add_column('Skills Count', style='green', justify='right')
    for domain, count in sorted(stats['domain_breakdown'].items(), key=lambda x: x[1], reverse=True):
        table.add_row(domain, str(count))
    console.print(table)
    console.print(f"[bold green]✨ Total Catalog: {stats['total_skills']} Skills | {stats['total_domains']} Domains | {stats['total_indexed_keywords']} Indexed Terms[/bold green]")

