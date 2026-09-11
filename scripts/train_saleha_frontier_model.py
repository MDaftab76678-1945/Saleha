"""
Saleha: Frontier Model Training Run

Runs FrontierTrainer.run_training(), which executes real phases and
honestly reports what it could not do:
- Phase 1 (SFT): real PEFT/TRL LoRA training.
- Phase 2 (DPO): real trl.DPOTrainer run, only when a real preference
  dataset with enough pairs exists; otherwise reported skipped with the
  reason -- no fake pairs are substituted.
- Phase 3 (RLIF): not implemented; reported as a gap, not simulated.
- Deployment + benchmark: real GGUF conversion via `ollama create` and real
  sandboxed Pass@1 evaluation, not invented scores.

See saleha/core/frontier_trainer.py for the full contract.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from saleha.core.frontier_trainer import FrontierTrainer


def main():
    console = Console()
    console.print("\n" + "=" * 70, style="bold cyan")
    console.print("[bold white on blue] SALEHA FRONTIER MODEL TRAINING RUN [/]", justify="center")
    console.print("=" * 70, style="bold cyan")
    console.print("[dim]Real multi-phase local fine-tuning; unimplemented phases are reported, not faked[/dim]\n")

    trainer = FrontierTrainer()
    report = trainer.run_training(base_model="qwen2.5-coder:3b", output_model="saleha-frontier")

    console.print(f"\n[bold green]Run complete in {report.training_duration_sec}s[/bold green]\n")

    phase_table = Table(title="Phase Outcomes", border_style="cyan")
    phase_table.add_column("Status", style="bold", justify="center")
    phase_table.add_column("Phase", style="white")
    for p in report.phases_completed:
        phase_table.add_row("[bold green]completed[/]", p)
    for p in report.phases_skipped:
        phase_table.add_row("[bold yellow]skipped[/]", p)
    console.print(phase_table)

    summary_lines = [
        f"[bold]Base Model:[/] {report.base_model} -> [bold]Output Model:[/] {report.target_model_name}",
        f"[bold]SFT succeeded:[/] {report.sft_result.success if report.sft_result else False}",
        f"[bold]DPO preference pairs found:[/] {report.total_dpo_pairs}",
    ]
    if report.dpo_final_loss is not None:
        summary_lines.append(f"[bold]DPO final loss:[/] {report.dpo_final_loss}")
    summary_lines.append(f"[bold]Adapter artifact:[/] {report.adapter_artifact_path}")
    summary_lines.append(f"[bold]Deployed to Ollama:[/] {report.deployed_to_ollama}")
    if report.benchmark_before_pass_rate is not None:
        summary_lines.append(f"[bold]Benchmark pass rate before:[/] {report.benchmark_before_pass_rate}")
    if report.benchmark_after_pass_rate is not None:
        summary_lines.append(f"[bold]Benchmark pass rate after:[/] {report.benchmark_after_pass_rate}")
    if report.error:
        summary_lines.append(f"[bold red]Error:[/] {report.error}")

    console.print(Panel("\n".join(summary_lines), title="Training Run Report", border_style="cyan"))


if __name__ == "__main__":
    main()
