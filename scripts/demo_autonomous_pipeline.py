"""Demo: End-to-End Autonomous Pipeline in Saleha.

Demonstrates:
1. AgentPC: Booting virtual workstation with isolated filesystem and Win32 Job Object sandbox.
2. Defect Detection: Running physical tests on flawed code (hardware exit code != 0).
3. Process Reward Model (PRM): Step-level credit assignment and early subtree pruning.
4. Verified Self-Correction: Closed-loop repair in AgentPC with Lyapunov stability defense.
5. Formal Verification (RLHVR): Sandbox exit code 0 + Z3 SMT contract proof.
6. RLCD & DPO: Synthesizing verified contrastive pairs and exporting to preference store.
7. Cryptographic Flight Recorder: Auditing the SHA-256 blackbox ledger.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from saleha.core.sandbox.agent_pc import AgentPC
from saleha.core.alignment.verifiable_rewards import RLHVRVerifier
from saleha.core.alignment.contrastive_rlcd import RLCDGenerator
from saleha.core.alignment.prm_mcts_engine import ProcessRewardModel
from saleha.core.loop.self_correction import VerifiedSelfCorrectionEngine

console = Console()


def run_autonomous_demo() -> None:
    console.print(Panel.fit("[bold cyan]SALEHA AUTONOMOUS REASONING & ALIGNMENT PIPELINE[/bold cyan]", border_style="cyan"))

    # Stage 1: Boot AgentPC
    console.print("\n[bold yellow]Stage 1: Booting Agent Personal Computer (AgentPC)...[/bold yellow]")
    pc = AgentPC(agent_role="coder_demo")
    console.print(f"  [green]OK[/green] Jailed WorkspaceFS: {pc.workspace_root}")
    console.print(f"  Sandbox: job object, {pc.sandbox.memory_limit_mb}MB cap (enforced on Windows only)")
    console.print("  [green]OK[/green] Blackbox Flight Recorder: SHA-256 hash-chained ledger")

    # Stage 2: Flawed Code Injection
    console.print("\n[bold yellow]Stage 2: Injecting Algorithmic Challenge with Edge Case Defect...[/bold yellow]")
    flawed_code = '''"""Portfolio Risk Calculator with weighted exposures."""
from typing import List, Dict, Any, Optional

def calculate_portfolio_risk(weights: List[float], exposures: List[float], hedge_ratio: float) -> float:
    """Calculates net portfolio risk with hedge ratio scaling."""
    assert len(weights) == len(exposures), "Weights and exposures length mismatch"
    total_exposure = sum(w * e for w, e in zip(weights, exposures))
    # Unhandled division by zero hazard if hedge_ratio is 0.0
    adjusted_risk = total_exposure / hedge_ratio
    return round(adjusted_risk, 4)
'''

    test_code = '''
# Test 1: Standard case
assert calculate_portfolio_risk([0.5, 0.5], [100.0, 200.0], 2.0) == 75.0

# Test 2: Edge case - Zero hedge ratio (fails with ZeroDivisionError on initial code)
assert calculate_portfolio_risk([0.5, 0.5], [100.0, 200.0], 0.0) == 0.0
'''

    pc.write_in_pc("portfolio_risk.py", flawed_code)
    pc.write_in_pc("test_portfolio_risk.py", test_code)

    # Stage 3: Physical RLHVR Execution (Baseline Check)
    console.print("\n[bold yellow]Stage 3: Running Physical Sandbox Execution (RLHVR Baseline)...[/bold yellow]")
    verifier = RLHVRVerifier(timeout_sec=5.0)
    baseline_signal = verifier.verify_code(flawed_code, test_code=test_code)

    console.print(f"  Hardware Exit Code: [red]{baseline_signal.details.get('sandbox_exit_code', -1)}[/red]")
    console.print(f"  Sandbox Passed: [red]{baseline_signal.passed_tests}[/red]")
    console.print(f"  Hardware Reward: [red]{baseline_signal.hardware_reward:+.3f}[/red]")
    console.print(f"  Error: [dim]{baseline_signal.details.get('sandbox_error', '').strip()[:100]}...[/dim]")

    # Stage 4: Process Reward Model (PRM) Decomposition
    console.print("\n[bold yellow]Stage 4: Process Reward Model (PRM) Step Breakdown...[/bold yellow]")
    prm = ProcessRewardModel()
    steps = prm.decompose_code_to_steps(flawed_code)

    table = Table(title="PRM Step Credit Assignment", safe_box=True)
    table.add_column("Step", justify="center", style="cyan bold")
    table.add_column("Type", style="bold")
    table.add_column("PRM Score", justify="right")
    table.add_column("Status", justify="center")

    for s in steps:
        score_color = "green" if s.prm_score >= 0.7 else "yellow" if s.prm_score >= 0.4 else "red"
        status_text = "[green]VALID[/green]" if s.is_valid else "[red]PRUNED[/red]"
        table.add_row(str(s.step_index), s.step_type, f"[{score_color}]{s.prm_score:.3f}[/]", status_text)
    console.print(table)

    # Stage 5: Autonomous Verified Self-Correction
    console.print("\n[bold yellow]Stage 5: Autonomous Self-Correction & Lyapunov Stability...[/bold yellow]")
    corrector = VerifiedSelfCorrectionEngine(pc=pc, max_iterations=4, verifier=verifier)
    result = corrector.correct_code(
        failing_code=flawed_code,
        test_code=test_code,
        task_description="Fix zero division when hedge ratio is zero",
    )

    console.print(f"  Self-Correction Success: [green]{result.success}[/green]")
    console.print(f"  Iterations Used: [bold]{result.iterations_count}[/bold]")
    console.print(f"  Lyapunov Status: [cyan bold]{result.lyapunov_status}[/cyan bold]")
    console.print(f"  Duration: [bold]{result.duration_ms:.2f} ms[/bold]")
    console.print(f"  Hardware Reward: [green]{result.final_reward.hardware_reward:+.3f}[/green]" if result.final_reward else "")
    console.print(f"  Composite Score: [green]{result.final_reward.composite_score:+.3f}[/green]" if result.final_reward else "")

    # Stage 6: RLCD Contrastive Pair Synthesis & DPO Export
    console.print("\n[bold yellow]Stage 6: Synthesizing RLCD Contrastive Pair & DPO Export...[/bold yellow]")
    rlcd = RLCDGenerator(verifier=verifier, min_margin=0.10)
    pair = rlcd.synthesize_pair_from_candidates(
        prompt="Write a safe portfolio risk calculator with zero hedge ratio defense",
        baseline_code=flawed_code,
        revised_code=result.repaired_code,
        critique="The original code failed with ZeroDivisionError when hedge_ratio was 0.0.",
        test_code=test_code,
    )

    if pair:
        console.print(f"  [green]OK[/green] Synthesized Contrastive Pair: [cyan]{pair.pair_id}[/cyan]")
        console.print(f"  Chosen Reward: [green]{pair.chosen_reward:+.3f}[/green] vs Rejected: [red]{pair.rejected_reward:+.3f}[/red]")
        console.print(f"  Physical Margin Delta: [bold green]{pair.margin_score:+.3f}[/bold green]")

        console.print("  Not recorded: demo pairs stay out of the real preference store.")

    # Stage 7: Blackbox Flight Recorder Audit
    console.print("\n[bold yellow]Stage 7: Cryptographic Flight Recorder Ledger Audit...[/bold yellow]")
    integrity = pc.blackbox.verify_integrity()
    console.print(f"  SHA-256 Blockchain Status: [bold green]{integrity['status']}[/bold green]")
    console.print(f"  Total Audit Events: [bold]{integrity['total_events']}[/bold]")

    console.print()
    ok = result.success and integrity["valid"]
    colour = "green" if ok else "red"
    verdict = "self-correction passed and ledger intact" if ok else "FAILED - see stages above"
    console.print(Panel.fit(f"[bold {colour}]DEMO RESULT: {verdict}[/bold {colour}]", border_style=colour))


if __name__ == "__main__":
    run_autonomous_demo()
