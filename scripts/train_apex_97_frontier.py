"""
Print the Apex-97 targets, and run the one check here that is real.

## What this script used to print

It rendered three progress bars, waited, and then announced:

    SALEHA HAS OFFICIALLY ACHIEVED 97.0%+ ACROSS ALL ARENAS!

    Overall Apex Average Score: 97.80%
    Status Across All 8 Domains:  100% OF DOMAINS ACHIEVED >= 97.0%
    Zero Subtle Hallucinations: Enforced via 3.42s InfoNCE Contrastive Separation
    Mathematical Invariant Proofs: 100% Verified via Symbolic SMT Hoare Triples

with a per-domain table of "Saleha Achieved" scores, each marked "Rank #1" and
"CERTIFIED". Nothing there was measured:

  * the three progress bars were `for _ in range(100): time.sleep(0.003)`.
    No training ran. Nothing was loaded. The bars existed to look like work.
  * the eight domain scores were literals in `apex_97_validator.py`, and
    `all_domains_passed_97` was `all()` over a list of literal `True`s -- it
    could not have returned False.
  * the "3.42 sigma InfoNCE" line came from `extreme_contrastive_trainer`,
    which returned `final_loss 0.12, sigma 3.42` whether it was given 5
    triplets or 500, and whose every "hard negative" was the same
    binary-search off-by-one regardless of the prompt. That module is deleted.

This is the failure that produced `saleha-asi`: it was trained on datasets
carrying fabricated "100% benchmark score" rows, and when finally tested on
real held-out tasks it scored **0/5**, failing even fibonacci.

## What it prints now

The targets, labelled as targets, plus the one thing in the original script
that genuinely ran: a Z3 division-safety proof over a sample function. That
part reports whether z3 is installed rather than assuming it.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.core.formal_smt_verifier import formal_smt_verifier
from saleha.core.apex_97_validator import apex_97_validator


def main() -> int:
    console = Console()

    console.print(Panel(
        "[bold yellow]These are TARGETS, not results.[/]\n\n"
        "No benchmark is executed here: this script trains nothing, loads no "
        "model and queries no leaderboard. The numbers below are goals "
        "recorded in the source, and the report says so itself via "
        "`is_measured=False`.\n\n"
        "To measure anything real, run a harness that executes the tasks -- "
        "for example `saleha benchmark`, which runs code and checks whether "
        "it passes.",
        title="Apex-97 targets", border_style="yellow"))
    console.print()

    # The one real check in the original script.
    sample = ("def safe_ratio(a: int, b: int) -> float:\n"
              "    if b == 0:\n"
              "        return 0.0\n"
              "    return a / b\n")
    proof = formal_smt_verifier.verify_function_contract(
        sample, function_name="safe_ratio")
    if proof.z3_available:
        console.print(Panel(
            f"  divisions found   : {proof.divisions_found}\n"
            f"  proven safe by Z3 : {proof.divisions_proven_safe}\n"
            f"  not analysable    : {proof.divisions_not_analyzed}\n"
            f"  duration          : {proof.proof_duration_ms} ms\n\n"
            f"{proof.mathematical_certificate}",
            title="Z3 division-safety proof (measured)", border_style="cyan"))
    else:
        console.print(Panel(
            "[yellow]z3-solver is not installed, so no proof was attempted.[/]\n"
            "Install it with: pip install \"saleha[formal]\"",
            title="Z3 division-safety proof", border_style="yellow"))
    console.print()

    report = apex_97_validator.run_apex_certification()
    table = Table(title="Apex-97 aspirational targets", border_style="yellow")
    table.add_column("Domain", style="white")
    table.add_column("Target", justify="right", style="yellow")
    table.add_column("Measured?", justify="center")
    for domain in report.domains:
        table.add_row(domain.domain_name, f"{domain.target_score:.1f}%", "[red]no[/]")
    console.print(table)
    console.print()

    console.print(f"[dim]{report.status_note}[/]")
    console.print(f"[dim]is_measured = {report.is_measured} | "
                  f"generated {report.timestamp}[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
