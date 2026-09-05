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

@cli.group()
def user():
    """Manage accounts that can sign in to the web Studio and admin panel."""

@user.command(name='create')
@click.argument('username')
@click.option('--admin', 'is_admin', is_flag=True, help='Grant the admin role')
@click.option('--password', default=None, help='Prompted for securely if omitted')
def user_create(username, is_admin, password):
    """Create an account. Run this once to bootstrap the first admin."""
    from saleha.core.user_store import ROLE_ADMIN, ROLE_USER, UserStoreError, user_store
    if password is None:
        password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    try:
        created = user_store.create_user(username, password, ROLE_ADMIN if is_admin else ROLE_USER)
    except UserStoreError as err:
        console.print(f'[bold red]Could not create user:[/] {err}')
        raise SystemExit(1)
    console.print(f'[bold green]Created[/] {created.username} with role [cyan]{created.role}[/]')

@user.command(name='list')
def user_list():
    """List accounts."""
    from saleha.core.user_store import user_store
    accounts = user_store.list_users()
    if not accounts:
        console.print('[dim]No accounts yet. Create one with: saleha user create <name> --admin[/]')
        return
    for account in accounts:
        state = '[red]disabled[/]' if account.disabled else '[green]active[/]'
        last = account.last_login_at or 'never'
        console.print(f'  {account.username:20} {account.role:8} {state}  last login: {last}')

@user.command(name='passwd')
@click.argument('username')
@click.option('--password', default=None, help='Prompted for securely if omitted')
def user_passwd(username, password):
    """Change an account's password. Signs that account out everywhere."""
    from saleha.core.user_store import UserStoreError, user_store
    if password is None:
        password = click.prompt('New password', hide_input=True, confirmation_prompt=True)
    try:
        user_store.set_password(username, password)
    except UserStoreError as err:
        console.print(f'[bold red]Could not change password:[/] {err}')
        raise SystemExit(1)
    console.print(f'[bold green]Password updated[/] for {username}; existing sessions revoked.')

@user.command(name='delete')
@click.argument('username')
@click.confirmation_option(prompt='Delete this account?')
def user_delete(username):
    """Delete an account."""
    from saleha.core.user_store import UserStoreError, user_store
    try:
        user_store.delete_user(username)
    except UserStoreError as err:
        console.print(f'[bold red]Could not delete user:[/] {err}')
        raise SystemExit(1)
    console.print(f'[bold green]Deleted[/] {username}')

