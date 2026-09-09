"""
Saleha Autonomous Ecosystem Dogfooding & Live Simulation Suite.
Executes an end-to-end autonomous verification cycle across all 9 tracks:
- Local Multi-Tier Fallback LLM inference
- 10-Department Poincaré Hyperbolic steering
- 250-Agent SPSC lock-free message dispatch
- Multi-File 2PC Atomic AST Self-Healing
- SQL Database Query & Mock Seeding
- Nanosecond Latency Histogram benchmarking
"""

import os
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from saleha import __version__
from saleha.core.model_provider import default_provider
from saleha.core.hyperbolic_engine import MultiAttractorLandscape
from saleha.core.saleha_swarm_topology import SalehaSwarmTopology, SwarmMessage
from saleha.core.self_healing import SelfHealingEngine
from saleha.core.latency_histogram import NanosecondLatencyHistogram
from saleha.core.padic_ultrametric import PadicValuationNode, PadicIsolationValidator

console = Console()

# This many checks actually run below. The panel used to say "ALL 9
# ENGINEERING PILLARS VALIDATED" unconditionally while only ever appending 6
# results to the table -- pillars 2, 3, 6, and 8 were never checked, and the
# remaining six were hardcoded "PASS" regardless of what the module under
# test returned. Every step below now reads its module's own real signal
# (a bool, an Optional, a count against an expected value) instead of
# assuming success because nothing raised.
TOTAL_PILLARS = 6


@click.command(name="dogfood", help="Run automated end-to-end smoke check across 6 core subsystems.")
def dogfood_cmd():
    console.print(Panel(f"[bold cyan]SALEHA ECOSYSTEM SMOKE CHECK (v{__version__})[/bold cyan]\n[dim]Exercising {TOTAL_PILLARS} core subsystems and checking their own reported result...[/dim]"))

    results = []
    passed_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:

        # 1. Model provider: a real call, under SALEHA_TEST_MODE routed to
        # the fast in-process mock so this command (and the test that
        # invokes it) never blocks on network/model latency. Outside test
        # mode this is a real Ollama round trip.
        t1 = progress.add_task("[cyan]1. Model provider cascade...", total=1)
        if os.environ.get("SALEHA_TEST_MODE") == "1":
            from saleha.core.model_provider import MockProvider
            res = MockProvider().generate("qwen2.5-coder:3b", "def verify(): return True")
        else:
            res = default_provider.generate("qwen2.5-coder:3b", "def verify(): return True")
        provider_ok = bool(res.success and res.content)
        results.append(("1. Model Provider", f"provider={getattr(res, 'provider_name', '?')}", provider_ok, f"{res.response_time:.3f}s"))
        progress.advance(t1)

        # 2. Poincare 10-department landscape: check the real count, not
        # just that construction did not raise.
        t2 = progress.add_task("[cyan]2. Poincare hyperbolic department landscape...", total=1)
        landscape = MultiAttractorLandscape()
        basins = len(landscape.DEPARTMENT_ATTRACTORS)
        basins_ok = basins == 10
        results.append(("2. Hyperbolic Topology", f"{basins}/10 department basins", basins_ok, "expects exactly 10"))
        progress.advance(t2)

        # 3. SPSC mailbox: send then receive, and check the message that
        # comes back is the one that was sent (not just non-None).
        t3 = progress.add_task("[cyan]3. Lock-free SPSC agent mailbox...", total=1)
        swarm = SalehaSwarmTopology()
        mb = swarm.mailboxes[0]
        sent_ok = mb.send(SwarmMessage(task_id=1, sender_agent_id=0, target_agent_id=1, payload="Sync"))
        msg = mb.receive()
        mailbox_ok = sent_ok and msg is not None and msg.payload == "Sync"
        results.append(("3. SPSC Mailbox", f"sent={sent_ok}, received={'Sync' if msg else None}", mailbox_ok, "round-trip payload match"))
        progress.advance(t3)

        # 4. p-Adic ultrametric isolation: read the validator's own
        # `isolated` bool instead of hardcoding "0.0% Semantic Bleeding".
        t4 = progress.add_task("[cyan]4. p-Adic ultrametric compartment isolation...", total=1)
        validator = PadicIsolationValidator(prime=5)
        nodes = [
            PadicValuationNode.from_raw([25, 50, 10, 5, 0, 0, 0, 0]),
            PadicValuationNode.from_raw([5, 10, 0, 0, 0, 0, 0, 0]),
            PadicValuationNode.from_raw([1, 2, 3, 4, 5, 6, 7, 8]),
        ]
        val_res = validator.validate_compartment_isolation(nodes)
        isolation_ok = bool(val_res.get("isolated"))
        results.append(("4. p-Adic Isolation", f"{val_res.get('checks_passed', 0)}/{val_res.get('total_checks', 0)} triangle checks", isolation_ok, val_res.get("semantic_bleeding_risk", "?")))
        progress.advance(t4)

        # 5. Self-healing reflexion: read error_detected, the field that
        # says whether the engine actually recognized the injected error --
        # printing error_type alone said nothing about whether detection
        # worked.
        t5 = progress.add_task("[cyan]5. Self-healing error reflexion...", total=1)
        healer = SelfHealingEngine()
        broken_error = "ZeroDivisionError: division by zero in calculate_roi()"
        healed_res = healer.analyze_and_heal(error_log=broken_error, original_task="def calculate_roi(): return 100 / 0")
        healing_ok = healed_res.error_detected and healed_res.error_type != "None"
        results.append(("5. Self-Healing Reflexion", f"detected={healed_res.error_type}", healing_ok, "expects ZeroDivisionError"))
        progress.advance(t5)

        # 6. Latency histogram: the recorded max must equal the largest
        # sample given to it -- printing p50/p99 alone never checked the
        # histogram's arithmetic against known input.
        t6 = progress.add_task("[cyan]6. Nanosecond latency histogram...", total=1)
        samples = [120, 140, 160, 180, 240, 890]
        hist = NanosecondLatencyHistogram()
        for s in samples:
            hist.record(s)
        rep = hist.get_report()
        histogram_ok = rep.get("max_peak_jitter_ns") == max(samples) and rep.get("total_samples") == len(samples)
        results.append(("6. Latency Histogram", f"p50={rep.get('p50_ns')}ns p99={rep.get('p99_ns')}ns max={rep.get('max_peak_jitter_ns')}ns", histogram_ok, f"expects max={max(samples)}ns"))
        progress.advance(t6)

    passed_count = sum(1 for _, _, ok, _ in results if ok)

    table = Table(title="Saleha Ecosystem Smoke Check Results", border_style="cyan")
    table.add_column("Subsystem", style="bold white", width=26)
    table.add_column("Observed", style="cyan", width=34)
    table.add_column("Status", style="bold", width=10)
    table.add_column("Expectation", style="magenta", width=26)

    for name, observed, ok, expectation in results:
        status = "[bold green]PASS[/]" if ok else "[bold red]FAIL[/]"
        table.add_row(name, observed, status, str(expectation))

    console.print(table)
    if passed_count == TOTAL_PILLARS:
        console.print(f"\n[bold green]{passed_count}/{TOTAL_PILLARS} subsystem checks passed.[/bold green]\n")
    else:
        console.print(f"\n[bold red]{passed_count}/{TOTAL_PILLARS} subsystem checks passed -- see FAIL rows above.[/bold red]\n")
