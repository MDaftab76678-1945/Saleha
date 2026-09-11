"""
Saleha Release Manifest Generator CLI.

Generates a manifest recording the actual, measured state of a release:
- Real pytest run against saleha/tests/, real pass/fail counts.
- A SHA3-derived key fingerprint from pqc_guard.Sha3VaultGuard (NOT
  post-quantum cryptography -- see saleha/core/pqc_guard.py docstring;
  this is a content fingerprint, not a signature scheme, and nothing here
  claims to sign the release).

This command does not build, package, or produce any distribution
artifact (.msi/.whl/Docker image/etc). A prior version of this file
claimed it did ("PQC Signed", "ASan Verified", "Gamma AST Certified", all
unconditional "READY"/"SIGNED" status) and printed a hardcoded
"696/696 PASSED (100% GREEN)" test result without ever running a test --
fixed to run pytest for real and report what actually happened.
"""

import json
import os
import subprocess
import sys
import time
import hashlib
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from saleha import __version__
from saleha.core.pqc_guard import sha3_vault_guard

console = Console()


def _run_test_suite() -> dict:
    """Runs the real test suite and returns a parsed pass/fail summary."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "saleha/tests/", "-q", "--no-header"],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except Exception as e:
        return {"ran": False, "summary": f"Could not run test suite: {e}"}

    output = (proc.stdout + proc.stderr).strip()
    last_line = output.splitlines()[-1] if output else ""
    return {
        "ran": True,
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "summary": last_line,
    }


@click.command(name="release", help="Generate a release manifest recording real test results and a content fingerprint.")
@click.option("--channel", "-c", default="stable", help="Release channel (stable, beta, nightly).")
@click.option("--skip-tests", is_flag=True, help="Skip running the test suite (manifest will record ran=False).")
def release_cmd(channel: str, skip_tests: bool):
    console.print(Panel(
        f"[bold gold1]Saleha Release Manifest (v{__version__})[/bold gold1]\n"
        f"[dim]Channel: {channel.upper()}[/dim]",
        border_style="gold1"
    ))

    if skip_tests:
        test_result = {"ran": False, "summary": "Skipped by --skip-tests"}
    elif os.environ.get("SALEHA_TEST_MODE") == "1":
        # Never spawn a real nested pytest run of the whole suite from
        # inside the suite itself -- this command is itself exercised by
        # saleha/tests/test_release_cli.py, and without this guard a run
        # under pytest would recursively invoke the entire suite as a
        # subprocess of one of its own tests.
        test_result = {"ran": False, "summary": "Skipped: SALEHA_TEST_MODE=1"}
    else:
        console.print("[dim]Running saleha/tests/ ...[/dim]")
        test_result = _run_test_suite()

    km = sha3_vault_guard.generate_key_material()
    release_manifest = {
        "platform": "Saleha",
        "version": __version__,
        "channel": channel,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "test_suite": test_result,
        "content_fingerprint_algorithm": "SHA3-512 (NOT a digital signature, NOT post-quantum)",
        "content_fingerprint": hashlib.sha256(km.public_key_b64.encode()).hexdigest()[:16],
    }

    manifest_path = "saleha-release-manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(release_manifest, f, indent=2)

    table = Table(title="Release Manifest", border_style="gold1")
    table.add_column("Field", style="bold white")
    table.add_column("Value", style="cyan")
    table.add_row("Test suite ran", str(test_result.get("ran")))
    table.add_row("Test suite result", str(test_result.get("summary", "")))
    table.add_row("Manifest path", manifest_path)
    console.print(table)

    if test_result.get("ran") and not test_result.get("passed", True):
        console.print(f"\n[bold red]Release manifest written, but the test suite did not pass.[/bold red]\n")
    else:
        console.print(f"\n[bold green]Release manifest for v{__version__} written to {manifest_path}.[/bold green]\n")

