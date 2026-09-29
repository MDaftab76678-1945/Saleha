"""
Saleha Live Terminal UI Dashboard (salehatop / saleha doom top).

Shows only data that is actually measured or recorded:
1. Hardware: CPU, RAM (psutil) and GPU memory when `nvidia-smi` is present.
2. Recent runs: the last entries of the persisted task history, so a run made
   by a different `saleha` process is visible here.
3. In-process message-bus activity: event counts per event type and sender.
4. The most recent message-bus events.

An earlier version of this dashboard drew RAM/VRAM/throughput from formulas of
a tick counter, a 250-cell "agent activity" grid from modulo arithmetic, fixed
legend counts, and randomly chosen invented log lines. None of that was measured
and all of it is gone; a source with no data now says so instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from typing import List, Optional, Tuple

import psutil
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from saleha import __version__

if sys.platform == "win32":
    try:
        reconfig_out = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfig_out):
            reconfig_out(encoding="utf-8", errors="replace")
        reconfig_err = getattr(sys.stderr, "reconfigure", None)
        if callable(reconfig_err):
            reconfig_err(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(safe_box=True)

_GIB = 1024 ** 3


def query_gpu_memory() -> Optional[Tuple[int, int]]:
    """Returns (used_mib, total_mib) for the first GPU, or None if it cannot be read."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding="utf-8", timeout=5,
        )
        if out.returncode != 0:
            return None
        used, total = (int(x.strip()) for x in out.stdout.splitlines()[0].split(","))
        return used, total
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _bar(fraction: float, width: int = 30) -> str:
    filled = max(0, min(width, round(fraction * width)))
    return "#" * filled + "-" * (width - filled)


class SalehaTopDashboard:
    def __init__(self) -> None:
        self.tick = 0

    def generate_header(self) -> Panel:
        title = Text()
        title.append("SALEHATOP: LIVE MONITOR ", style="bold green")
        title.append(f"v{__version__} ", style="bold cyan")
        title.append(f"| {datetime.now().strftime('%H:%M:%S')} | ", style="dim")
        title.append(f"PID: {os.getpid()}", style="bold yellow")
        return Panel(title, border_style="cyan", padding=(0, 1))

    def generate_hardware_panel(self) -> Panel:
        mem = psutil.virtual_memory()
        proc_rss = psutil.Process().memory_info().rss
        text = Text()
        text.append(" CPU Usage:  ", style="bold white")
        cpu = psutil.cpu_percent(interval=None)
        text.append(f"[{_bar(cpu / 100)}] {cpu:.0f}%\n", style="green")

        text.append(" RAM Usage:  ", style="bold white")
        text.append(f"[{_bar(mem.percent / 100)}] ", style="green")
        text.append(f"{mem.used / _GIB:.1f} / {mem.total / _GIB:.1f} GB ({mem.percent:.0f}%)\n", style="bold green")

        text.append(" This process: ", style="bold white")
        text.append(f"{proc_rss / 1024 ** 2:.0f} MB resident\n", style="bold magenta")

        text.append(" GPU Memory: ", style="bold white")
        gpu = query_gpu_memory()
        if gpu is None:
            text.append("n/a (nvidia-smi not available)", style="dim")
        else:
            used, total = gpu
            text.append(f"[{_bar(used / total)}] {used} / {total} MiB", style="bold cyan")

        return Panel(text, title="Hardware", border_style="green")

    def generate_recent_runs_panel(self, limit: int = 10) -> Panel:
        from saleha.core.task_history import TaskHistory

        try:
            records = TaskHistory().recent(limit)
        except Exception as exc:  # unreadable history must not kill the monitor
            return Panel(f"Task history unreadable: {exc}", title="Recent Runs", border_style="red")
        if not records:
            return Panel("No runs recorded yet.", title="Recent Runs", border_style="yellow")

        table = Table(expand=True, show_edge=False)
        table.add_column("Time", style="dim", no_wrap=True)
        table.add_column("Result", no_wrap=True)
        table.add_column("Tries", justify="right", no_wrap=True, min_width=5)
        table.add_column("Model", style="cyan", no_wrap=True, max_width=16, overflow="ellipsis")
        table.add_column("Goal", overflow="ellipsis", no_wrap=True, ratio=1)
        for r in reversed(records):
            result = "[green]ok[/]" if r.success else "[red]failed[/]"
            table.add_row(str(r.timestamp)[11:19], result, str(r.attempts), str(r.model), r.goal[:60])
        return Panel(table, title=f"Recent Runs (last {len(records)})", border_style="yellow")

    def generate_bus_activity_table(self) -> Table:
        from saleha.core.swarm.agent_message_bus import message_bus

        table = Table(title="Message-bus activity (this process)", border_style="magenta", expand=True)
        table.add_column("Event type", style="bold white")
        table.add_column("Sender", style="cyan")
        table.add_column("Count", justify="right")
        counts = Counter((e.event_type, e.sender_agent) for e in message_bus.get_history(limit=500))
        if not counts:
            table.add_row("(no events)", "-", "0")
        for (event_type, sender), n in counts.most_common(12):
            table.add_row(str(event_type), str(sender), str(n))
        return table

    def generate_event_log(self) -> Panel:
        from saleha.core.swarm.agent_message_bus import message_bus

        events = message_bus.get_history(limit=6)
        if not events:
            body = Text("No message-bus events in this process. Run a swarm here to see its events.", style="dim")
        else:
            lines: List[str] = []
            for e in events:
                ts = datetime.fromtimestamp(e.timestamp).strftime("%H:%M:%S")
                lines.append(f"[bold cyan]- [{ts}][/] [yellow]{e.sender_agent}[/] dispatched [bold green]{e.event_type}[/]")
            body = Text.from_markup("\n".join(lines))
        return Panel(body, title="Latest message-bus events", border_style="blue")

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=8),
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["left"].split_column(
            Layout(name="hardware", size=8),
            Layout(name="runs", ratio=1),
        )
        layout["right"].update(self.generate_bus_activity_table())
        layout["header"].update(self.generate_header())
        layout["left"]["hardware"].update(self.generate_hardware_panel())
        layout["left"]["runs"].update(self.generate_recent_runs_panel())
        layout["footer"].update(self.generate_event_log())
        return layout

    def run(self, max_seconds: Optional[int] = None) -> None:
        start_time = time.time()
        with Live(self.make_layout(), refresh_per_second=4, screen=True) as live:
            try:
                while True:
                    self.tick += 1
                    live.update(self.make_layout())
                    time.sleep(0.25)
                    if max_seconds and (time.time() - start_time) >= max_seconds:
                        break
            except KeyboardInterrupt:
                pass


def run_salehatop(max_seconds: Optional[int] = None) -> None:
    SalehaTopDashboard().run(max_seconds=max_seconds)


if __name__ == "__main__":
    run_salehatop()
