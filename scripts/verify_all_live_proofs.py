"""
Saleha: live self-checks, reporting only what was actually measured.

Runs five checks against this machine and prints what each one found. Nothing
here is asserted in advance; every line is read off a real result.

## What this script used to do

It was the "All-in-One Empirical Live Proof Verification Suite", promising
"direct, undeniable physical proofs", and it ended with:

    "ALL 5 PHYSICAL & EMPIRICAL PROOFS VERIFIED WITH 100% SUCCESS!"

printed unconditionally, before any result was examined. Three separate
problems:

1. **The final banner was a constant.** It printed 100% success even when
   Proof 1 had just rendered rows reading "MISSING".
2. **The git line was a hardcoded string**: "100% Synced with origin/main
   (MDaftab76678-1945/Saleha)". Nothing compared anything. Measured while
   fixing this: HEAD was 22 commits ahead of `origin/main`, on a different
   branch, and the banner still said 100% synced.
3. **It crashed.** `formal_smt_verifier` was rewritten in an earlier pass to
   stop fabricating proofs -- it now reports `z3_available`, `divisions_found`
   and `divisions_proven_safe`. This script still read `proof.preconditions`
   and `proof.is_satisfiable`, which no longer exist, so it died with an
   AttributeError at check 2. It had not run since that pass and nobody
   noticed, because nothing runs it in CI.

Every check now reports its real outcome, the exit code is non-zero when any
check fails, and the summary counts what passed rather than announcing it.
"""

import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.core.formal_smt_verifier import formal_smt_verifier
from saleha.core.spics_fuzz_engine import spics_fuzz_engine
from saleha.core.hypergraph_indexer import hypergraph_indexer

DATASET_FILES = [
    "datasets/saleha_dpo_pairs.jsonl",
    "datasets/saleha_sft_10k.jsonl",
    "datasets/saleha_sft_10k_alpaca.json",
    "datasets/saleha_slm_train.jsonl",
]


def check_datasets(console: Console) -> bool:
    """Every declared dataset file exists and parses. Missing files fail."""
    table = Table(title="1. Training datasets on disk", border_style="cyan")
    table.add_column("File", style="white")
    table.add_column("Size", justify="right")
    table.add_column("Records", justify="right")
    table.add_column("Status")

    all_present = True
    for path in DATASET_FILES:
        if not os.path.exists(path):
            all_present = False
            table.add_row(path, "-", "-", "[red]MISSING[/]")
            continue
        size_kb = round(os.path.getsize(path) / 1024, 2)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                if path.endswith(".jsonl"):
                    count = sum(1 for line in fh if line.strip())
                else:
                    count = len(json.load(fh))
            table.add_row(path, f"{size_kb} KB", str(count), "[green]parsed[/]")
        except (OSError, ValueError) as exc:
            all_present = False
            table.add_row(path, f"{size_kb} KB", "-", f"[red]unreadable: {exc}[/]")

    console.print(table)
    return all_present


def check_smt(console: Console) -> bool:
    """
    Run the Z3 division-by-zero prover on a sample function.

    Reports `z3_available` honestly: without the solver installed there is no
    proof, and saying so is the result. The old code read fields that no longer
    exist and crashed here.
    """
    sample = (
        "def safe_ratio(a: int, b: int) -> float:\n"
        "    if b == 0:\n"
        "        return 0.0\n"
        "    return a / b\n"
    )
    proof = formal_smt_verifier.verify_function_contract(sample,
                                                        function_name="safe_ratio")
    if not proof.z3_available:
        console.print(Panel(
            "[yellow]z3-solver is not installed, so no proof was attempted.[/]\n"
            f"{proof.mathematical_certificate}",
            title="2. Formal SMT division-safety proof", border_style="yellow"))
        return False

    console.print(Panel(
        f"  divisions found        : {proof.divisions_found}\n"
        f"  proven safe by Z3      : {proof.divisions_proven_safe}\n"
        f"  not analysable         : {proof.divisions_not_analyzed}\n"
        f"  duration               : {proof.proof_duration_ms} ms\n\n"
        f"{proof.mathematical_certificate}",
        title="2. Formal SMT division-safety proof", border_style="cyan"))
    return proof.divisions_proven_safe == proof.divisions_found


def check_fuzz(console: Console) -> bool:
    """Fuzz a guarded function; anything below 100% resilience is a failure."""
    result = spics_fuzz_engine.fuzz_test_code(
        "def safe_divide(a, b):\n"
        "    if b == 0 or b is None or a is None:\n"
        "        return 0\n"
        "    return a / b\n",
        function_name="safe_divide",
        num_trials=50,
    )
    passed = result.passed_trials == result.total_fuzz_trials
    console.print(Panel(
        f"  trials      : {result.total_fuzz_trials}\n"
        f"  passed      : {result.passed_trials}\n"
        f"  resilience  : {result.invariant_resilience_pct}%\n"
        f"  duration    : {result.execution_time_ms} ms",
        title="3. Property-based fuzzing of a guarded function",
        border_style="green" if passed else "red"))
    return passed


def check_indexer(console: Console) -> bool:
    """Index saleha/core and require that it found something."""
    stats = hypergraph_indexer.scan_directory("saleha/core")
    ok = stats.total_files_scanned > 0 and stats.total_symbols_indexed > 0
    console.print(Panel(
        f"  files scanned    : {stats.total_files_scanned}\n"
        f"  symbols indexed  : {stats.total_symbols_indexed}\n"
        f"  dependency edges : {stats.total_dependency_edges}\n"
        f"  duration         : {stats.indexing_duration_ms} ms",
        title="4. AST symbol indexing over saleha/core",
        border_style="magenta" if ok else "red"))
    return ok


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def check_git(console: Console) -> bool:
    """
    Report the real branch, HEAD, upstream and dirty state.

    The old version printed "100% Synced with origin/main
    (MDaftab76678-1945/Saleha)" as a literal string. Measured at the time of
    this rewrite: HEAD was 22 commits ahead of origin/main, on a different
    branch, and the banner still claimed 100% synced.
    """
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    head = _git("rev-parse", "--short", "HEAD") or "(unknown)"
    message = (_git("log", "-1", "--pretty=%s") or "(none)")[:70]
    dirty = _git("status", "--porcelain")
    upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")

    if upstream:
        counts = _git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        behind, ahead = (counts.split() + ["?", "?"])[:2]
        sync = f"{ahead} ahead, {behind} behind {upstream}"
        in_sync = ahead == "0" and behind == "0"
    else:
        sync = "no upstream configured for this branch"
        in_sync = False

    dirty_count = len([ln for ln in dirty.splitlines() if ln.strip()])
    console.print(Panel(
        f"  branch       : {branch}\n"
        f"  HEAD         : {head}  {message}\n"
        f"  upstream     : {sync}\n"
        f"  working tree : "
        f"{'clean' if not dirty_count else f'{dirty_count} uncommitted change(s)'}",
        title="5. Git state", border_style="green" if in_sync else "yellow"))
    # Reported, never asserted: being ahead of your upstream is normal during
    # development and is not a failure of this script.
    return True


def main() -> int:
    console = Console()
    console.print("\nSaleha live self-checks\n" + "-" * 40)

    checks = [
        ("datasets", check_datasets),
        ("smt", check_smt),
        ("fuzz", check_fuzz),
        ("indexer", check_indexer),
        ("git", check_git),
    ]

    results = {}
    for name, fn in checks:
        try:
            results[name] = bool(fn(console))
        except Exception as exc:  # a broken check is a failed check
            console.print(Panel(f"[red]{type(exc).__name__}: {exc}[/]",
                                title=f"{name} (raised)", border_style="red"))
            results[name] = False
        console.print()

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    failed = [k for k, v in results.items() if not v]

    if failed:
        console.print(f"[bold red]{passed}/{total} checks passed.[/] "
                      f"Failed: {', '.join(failed)}")
    else:
        console.print(f"[bold green]{passed}/{total} checks passed.[/]")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
