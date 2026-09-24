"""CLI commands for the native Rust Intent Kernel (`ik`)."""

import os
import sys
from typing import Optional

import click
from rich.panel import Panel
from rich.syntax import Syntax

from saleha.cli.commands import cli, console
from saleha.core import intent_kernel


@cli.group(name="ik")
def ik_group() -> None:
    """Rust Native Sovereign Intent Kernel commands."""
    pass


@ik_group.command(name="status")
def status_cmd() -> None:
    """Check Rust intent kernel status and ledger integrity."""
    if not intent_kernel.is_available():
        console.print(f"[red]Intent kernel binary not found.[/red]\nBuild it with: {intent_kernel.BUILD_HINT}")
        return
    res = intent_kernel.get_status()
    if res.get("returncode") == 0:
        console.print(Panel(res.get("stdout", ""), title="Rust Intent Kernel Status", border_style="green"))
    else:
        console.print(f"[red]Failed to get kernel status:[/red] {res.get('stderr') or res.get('stdout')}")


@ik_group.command(name="run")
@click.argument("goal")
@click.option("--dry-run", is_flag=True, help="Simulate intent plan compilation without executing side effects")
@click.option("--proof", default=None, help="Custom proof ledger path")
@click.option("--timeout", default=120.0, type=float, help="Timeout in seconds")
def run_cmd(goal: str, dry_run: bool, proof: Optional[str], timeout: float) -> None:
    """Run an autonomous goal through the native Rust plan compiler and executor."""
    if not intent_kernel.is_available():
        console.print(f"[red]Intent kernel binary not found.[/red]\nBuild it with: {intent_kernel.BUILD_HINT}")
        sys.exit(1)
    console.print(f"[bold cyan]Dispatching to Rust Intent Kernel:[/bold cyan] {goal}")
    res = intent_kernel.run_mission(goal=goal, dry_run=dry_run, proof_path=proof, timeout=timeout)
    stdout = res.get("stdout", "")
    stderr = res.get("stderr", "")
    if res.get("returncode") == 0:
        console.print(Panel(stdout, title="Kernel Mission Execution Result", border_style="green"))
    else:
        console.print(Panel(stderr or stdout, title="Kernel Mission Error", border_style="red"))
        sys.exit(res.get("returncode", 1))


@ik_group.command(name="solve")
@click.argument("task")
@click.option("--language", "-l", default="python", help="Target programming language")
@click.option("--model", "-m", default="qwen2.5-coder:3b", help="Local Ollama model name")
@click.option("--max-attempts", default=5, type=int, help="Maximum reflexion attempts")
def solve_cmd(task: str, language: str, model: str, max_attempts: int) -> None:
    """Reflexion self-healing problem solving via Rust native loop."""
    if not intent_kernel.is_available():
        console.print(f"[red]Intent kernel binary not found.[/red]\nBuild it with: {intent_kernel.BUILD_HINT}")
        sys.exit(1)
    console.print(f"[bold cyan]Reflexion solve via Rust engine:[/bold cyan] {task} (model: {model})")
    res = intent_kernel.solve_task(task=task, language=language, model=model, max_attempts=max_attempts)
    if res.get("returncode") == 0:
        console.print(Panel(str(res.get("stdout", "")), title="Reflexion Solution", border_style="green"))
    else:
        err_msg = str(res.get("stderr") or res.get("stdout") or "Unknown error")
        console.print(Panel(err_msg, title="Reflexion Failure", border_style="red"))
        sys.exit(res.get("returncode", 1))


@ik_group.command(name="verify")
@click.option("--proof", default=".ik/proof.jsonl", help="Proof ledger path to verify")
def verify_cmd(proof: str) -> None:
    """Verify SHA-256 hash-chain cryptographic ledger integrity."""
    res = intent_kernel.verify_ledger(proof)
    if not res.get("available"):
        console.print(f"[red]Kernel unavailable:[/red] {res.get('detail')}")
        sys.exit(1)
    if res.get("valid"):
        console.print(f"[green]Ledger verified intact:[/green] {proof} ({res.get('events')} events)")
    else:
        console.print(f"[red]TAMPER DETECTED / INVALID CHAIN:[/red] {proof} ({res.get('detail')})")
        sys.exit(1)


@ik_group.command(name="arch")
def arch_cmd() -> None:
    """Print the native sovereign architecture map."""
    if not intent_kernel.is_available():
        console.print(f"[red]Intent kernel binary not found.[/red]\nBuild it with: {intent_kernel.BUILD_HINT}")
        return
    res = intent_kernel.get_architecture()
    console.print(Panel(res.get("stdout", ""), title="Rust Kernel Architecture", border_style="blue"))
