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

@cli.group(name='vault')
def vault_group():
    """Encrypted Secret & Credential Vault (PBKDF2-HMAC-SHA256)."""
    pass

@vault_group.command(name='set')
@click.argument('key')
@click.argument('value')
@click.option('--desc', default='', help='Description for this secret')
def vault_set_cmd(key, value, desc):
    """Store or update an encrypted secret in the vault."""
    from saleha.core.vault import vault
    ok = vault.set_secret(key, value, description=desc)
    if ok:
        console.print(f"[bold green]🔐 Secret '{key}' stored securely in encrypted vault.[/]")
    else:
        console.print(f"[bold red]❌ Failed to store secret '{key}'.[/]")

@vault_group.command(name='get')
@click.argument('key')
def vault_get_cmd(key):
    """Retrieve and decrypt a secret value from the vault."""
    from saleha.core.vault import vault
    val = vault.get_secret(key)
    if val is not None:
        click.echo(val)
    else:
        console.print(f"[bold red]Secret '{key}' not found in vault or environment.[/]")
        raise click.exceptions.Exit(1)

@vault_group.command(name='list')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def vault_list_cmd(as_json):
    """List all stored secrets with masked previews and timestamps."""
    from saleha.core.vault import vault
    secrets_list = vault.list_secrets()
    if as_json:
        payload = [{'key': s.key, 'preview': s.preview, 'created_at': s.created_at, 'updated_at': s.updated_at, 'description': s.description} for s in secrets_list]
        click.echo(json.dumps(payload, ensure_ascii=True))
        return
    if not secrets_list:
        console.print("[yellow]Vault is empty. Use 'saleha vault set <KEY> <VALUE>' to add secrets.[/]")
        return
    from rich.table import Table
    table = Table(title='🔐 Saleha Encrypted Secret Vault', border_style='cyan')
    table.add_column('Secret Key', style='bold cyan')
    table.add_column('Masked Preview', style='yellow')
    table.add_column('Description', style='dim')
    table.add_column('Last Updated', style='green')
    for s in secrets_list:
        table.add_row(s.key, s.preview, s.description or '-', s.updated_at)
    console.print(table)

@vault_group.command(name='delete')
@click.argument('key')
def vault_delete_cmd(key):
    """Delete a secret from the vault."""
    from saleha.core.vault import vault
    ok = vault.delete_secret(key)
    if ok:
        console.print(f"[bold green]🗑️ Secret '{key}' deleted from vault.[/]")
    else:
        console.print(f"[bold red]Secret '{key}' was not found in vault.[/]")

@vault_group.command(name='export')
def vault_export_cmd():
    """Inject all vault secrets into the current environment session."""
    from saleha.core.vault import vault
    exported = vault.export_to_env()
    console.print(f'[bold green]✅ Exported {len(exported)} secret(s) to environment.[/]')

