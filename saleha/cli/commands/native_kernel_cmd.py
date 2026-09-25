"""CLI commands for the native Rust Intent Kernel (`ik`)."""

import sys
from typing import Any, Dict, Optional

import click
from rich.panel import Panel

from saleha.cli.commands import cli, console
from saleha.core import intent_kernel


def _require_kernel() -> None:
    """Exit non-zero when the kernel binary is missing: "did not run" is not success."""
    if not intent_kernel.is_available():
        console.print(f"[red]Intent kernel binary not found.[/red]\nBuild it with: {intent_kernel.BUILD_HINT}")
        sys.exit(1)


def _error_text(res: Dict[str, Any]) -> str:
    """Kernel output for a failed call; a run that never started carries only 'detail'."""
    parts = [str(res.get(k) or "") for k in ("stdout", "stderr", "detail")]
    return "\n".join(p for p in parts if p) or "kernel returned no output"


def _exit_code(res: Dict[str, Any]) -> int:
    """Non-zero exit for any failed call, including one that never produced a returncode."""
    code = res.get("returncode")
    return code if isinstance(code, int) and code != 0 else 1


@cli.group(name="ik")
def ik_group() -> None:
    """Rust Native Sovereign Intent Kernel commands."""
    pass


@ik_group.command(name="status")
def status_cmd() -> None:
    """Check Rust intent kernel status and ledger integrity."""
    _require_kernel()
    res = intent_kernel.get_status()
    if res.get("returncode") == 0:
        console.print(Panel(res.get("stdout", ""), title="Rust Intent Kernel Status", border_style="green"))
    else:
        console.print(f"[red]Failed to get kernel status:[/red] {_error_text(res)}")
        sys.exit(_exit_code(res))


@ik_group.command(name="run")
@click.argument("goal")
@click.option("--dry-run", is_flag=True, help="Simulate intent plan compilation without executing side effects")
@click.option("--proof", default=None, help="Custom proof ledger path")
@click.option("--timeout", default=120.0, type=float, help="Timeout in seconds")
def run_cmd(goal: str, dry_run: bool, proof: Optional[str], timeout: float) -> None:
    """Run an autonomous goal through the native Rust plan compiler and executor."""
    _require_kernel()
    console.print(f"[bold cyan]Dispatching to Rust Intent Kernel:[/bold cyan] {goal}")
    res = intent_kernel.run_mission(goal=goal, dry_run=dry_run, proof_path=proof, timeout=timeout)
    if res.get("returncode") == 0:
        console.print(Panel(res.get("stdout", ""), title="Kernel Mission Execution Result", border_style="green"))
    else:
        console.print(Panel(_error_text(res), title="Kernel Mission Error", border_style="red"))
        sys.exit(_exit_code(res))


@ik_group.command(name="solve")
@click.argument("task")
@click.option("--language", "-l", default="python", help="Target programming language")
@click.option("--model", "-m", default="qwen2.5-coder:3b", help="Local Ollama model name")
@click.option("--max-attempts", default=5, type=int, help="Maximum reflexion attempts")
@click.option("--timeout", default=900.0, type=float,
              help="Timeout in seconds; each attempt makes up to six local model calls")
def solve_cmd(task: str, language: str, model: str, max_attempts: int, timeout: float) -> None:
    """Reflexion self-healing problem solving via Rust native loop."""
    _require_kernel()
    console.print(f"[bold cyan]Reflexion solve via Rust engine:[/bold cyan] {task} (model: {model})")
    res = intent_kernel.solve_task(task=task, language=language, model=model,
                                   max_attempts=max_attempts, timeout=timeout)
    if res.get("returncode") == 0:
        console.print(Panel(str(res.get("stdout", "")), title="Reflexion Solution", border_style="green"))
    else:
        console.print(Panel(_error_text(res), title="Reflexion Failure", border_style="red"))
        sys.exit(_exit_code(res))


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
    _require_kernel()
    res = intent_kernel.get_architecture()
    if res.get("returncode") != 0:
        console.print(f"[red]Failed to get kernel architecture:[/red] {_error_text(res)}")
        sys.exit(_exit_code(res))
    console.print(Panel(res.get("stdout", ""), title="Rust Kernel Architecture", border_style="blue"))
