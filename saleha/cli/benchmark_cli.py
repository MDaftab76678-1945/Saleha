"""
Saleha micro-benchmarks: four subsystem measurements taken on this machine.

Measures, all with `time.perf_counter()` around real loops:
- SPSC lock-free mailbox throughput (send+receive pairs/sec)
- Poincare hyperbolic distance latency, 16-D (distances/sec)
- Polyglot sandbox execution time for one python snippet (ms)
- Latency histogram record throughput (records/sec)

It does **not** compare Saleha against any other tool. The docstring used to
claim a "Competitive Index vs Devin, Cursor, and Lovable" and the command
printed "10x Faster", "$0.00 / Token" and "100% Deterministic" beneath the
results table -- none of it measured, no competing tool ever run. That block
is gone; see the comment where it used to be.
"""

import time
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from saleha import __version__
from saleha.core.saleha_swarm_topology import LockFreeMailbox, SwarmMessage
from saleha.core.latency_histogram import NanosecondLatencyHistogram
from saleha.core.polyglot_executor import polyglot_executor

console = Console()


@click.command(name="benchmark", help="Run comprehensive throughput and latency micro-benchmarks.")
@click.option("--iterations", "-n", default=10000, help="Number of benchmark iterations per test.")
def benchmark_cmd(iterations: int):
    console.print(Panel(f"[bold green]⚡ SALEHA AI MICRO-BENCHMARK & PERFORMANCE AUDIT (v{__version__})[/bold green]\n[dim]Benchmarking {iterations:,} operations per subsystem...[/dim]"))

    metrics = []

    # 1. SPSC Ring Buffer Throughput
    mb = LockFreeMailbox(capacity=64)
    msg = SwarmMessage(task_id=1, sender_agent_id=0, target_agent_id=1, payload="Bench")
    t0 = time.perf_counter()
    for _ in range(iterations):
        mb.send(msg)
        mb.receive()
    spsc_time = time.perf_counter() - t0
    spsc_ops = iterations / spsc_time if spsc_time > 0 else 0
    metrics.append(("SPSC Queue Throughput", f"{spsc_ops:,.0f} ops/sec", f"{(spsc_time/iterations)*1e6:.3f} μs/op", f"{iterations:,} send+receive pairs"))

    # 2. Poincaré Hyperbolic Distance Latency
    from saleha.core.hyperbolic_engine import HyperbolicVector
    vec_u = HyperbolicVector([0.1] * 16)
    vec_v = HyperbolicVector([0.2] * 16)
    t0 = time.perf_counter()
    for _ in range(min(iterations, 2000)):
        vec_u.hyperbolic_distance(vec_v)
    poincare_time = time.perf_counter() - t0
    poincare_ops = min(iterations, 2000) / poincare_time if poincare_time > 0 else 0
    metrics.append(("Poincaré Hyperbolic Math", f"{poincare_ops:,.0f} dist/sec", f"{(poincare_time/min(iterations, 2000))*1e6:.3f} μs/op", f"{min(iterations, 2000):,} distances, 16-D"))

    # 3. Polyglot Pre-Warmed Sandbox Cold-Start
    t0 = time.perf_counter()
    res = polyglot_executor.execute("x = 1 + 1", language="python")
    sandbox_ms = (time.perf_counter() - t0) * 1000
    metrics.append(("Sandbox Execution Time", f"{sandbox_ms:.2f} ms", f"{res.execution_time:.2f} ms runtime", "1 python execution"))

    # 4. Latency Histogram Allocation Overhead
    hist = NanosecondLatencyHistogram()
    t0 = time.perf_counter()
    for i in range(iterations):
        hist.record((i * 17) % 5000)
    hist_time = time.perf_counter() - t0
    hist_ops = iterations / hist_time if hist_time > 0 else 0
    metrics.append(("Latency Histogram", f"{hist_ops:,.0f} records/sec", f"{(hist_time/iterations)*1e6:.3f} μs/op", f"{iterations:,} records"))

    # Render Table
    table = Table(title="🚀 Saleha AI Hardware & Algorithmic Benchmark Scores", border_style="green")
    table.add_column("Subsystem / Benchmark", style="bold white", width=28)
    table.add_column("Throughput", style="cyan", width=22)
    table.add_column("Latency", style="magenta", width=20)
    table.add_column("What was run", style="dim", width=20)

    for sub, th, lat, gr in metrics:
        table.add_row(sub, th, lat, gr)

    console.print(table)
    # A "Competitive Index vs Market Tools (Cursor, Devin, Bolt.new)" block
    # used to print here: "10x Faster (Sub-100μs vs 20ms)", "$0.00 / Token",
    # "100% Deterministic". None of it was measured. No competing tool was
    # ever run, the 20ms it compared against came from nowhere, the AST
    # latency it claimed is not one of the four benchmarks above, and this
    # command never exercises the 2PC merge it called deterministic.
    #
    # That is the defect the `leaderboard` command was deleted for in pass
    # 30 -- our invented figure printed beside named competitors -- so the
    # block is removed rather than reworded. There is no honest version
    # without actually measuring the other tools.
    console.print(
        f"\n[dim]{len(metrics)} subsystems measured on this machine. "
        f"No comparison against other tools was performed.[/dim]\n"
    )
