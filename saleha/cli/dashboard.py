"""
Saleha CLI: Live Rich TUI Dashboard

A responsive, multi-pane visual operations dashboard rendering:
1. System status, active models, and memory cache health
2. Active agent profiles & loaded skills inventory
3. Model success rates, throughput, and memory stats
4. Real-time task history and execution audit records
"""

import os
import sys
import time
from typing import Optional
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

from saleha import __version__
from saleha.core.agent_profile_loader import profile_registry
from saleha.core.skill_registry import registry as skill_registry, load_builtin_skills
from saleha.core.memory_store import memory_store
from saleha.core.stats_tracker import StatsTracker
from saleha.core.task_history import TaskHistory
from saleha.core.audit_log import AuditLog
from saleha.core.smart_router import SmartRouter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(safe_box=True)


def create_header_panel() -> Panel:
    title = Text()
    title.append("🧠 SALEHA AI FRAMEWORK ", style="bold green")
    title.append(f"v{__version__} ", style="bold cyan")
    title.append("• MULTI-AGENT LIVE DASHBOARD • ", style="bold magenta")
    title.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
    return Panel(title, style="green", border_style="green")


def create_profiles_table() -> Table:
    table = Table(title="🎭 Active Agent Profiles", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Role Name", style="green")
    table.add_column("Ver", style="dim", justify="center")

    profiles = profile_registry.list_profiles()
    for p in sorted(profiles, key=lambda x: x.id)[:8]:
        table.add_row(p.id.replace("agent_", ""), p.name[:35], p.version)

    if len(profiles) > 8:
        table.add_row("...", f"+ {len(profiles) - 8} more profiles", "-")
    return table


def create_skills_table() -> Table:
    table = Table(title="⚡ Registered Skills", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Skill Name", style="cyan", no_wrap=True)
    table.add_column("Capability Scope", style="yellow")

    load_builtin_skills()
    skills = skill_registry.list_skills()
    for s in skills:
        table.add_row(s.name, s.description[:45] + "..." if len(s.description) > 45 else s.description)
    return table


def create_stats_table() -> Table:
    table = Table(title="📊 Model Performance", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Model", style="cyan")
    table.add_column("Uses", justify="right")
    table.add_column("Success", justify="right", style="green")
    table.add_column("Avg Tries", justify="right", style="yellow")

    tracker = StatsTracker()
    bucket = tracker._data.get("coding", {})
    if not bucket:
        table.add_row("No runs recorded yet", "-", "-", "-")
    else:
        for model_name, data in sorted(bucket.items(), key=lambda item: -item[1].get("uses", 0))[:5]:
            s = tracker.get_model_stats(model_name, "coding")
            table.add_row(model_name[:20], str(s.uses), f"{s.success_rate}%", str(s.avg_attempts))
    return table


def create_memory_panel() -> Panel:
    mem_stats = memory_store.stats()
    memories = memory_store.list_all(limit=4)

    text = Text()
    text.append(f"📦 Total Cached Solutions: {mem_stats['total_memories']}  |  🎯 Total Reused Hits: {mem_stats['total_hits']}\n", style="bold cyan")
    text.append("-" * 55 + "\n", style="dim")

    if not memories:
        text.append("No verified solutions cached yet. Run tasks to populate memory.", style="dim italic")
    else:
        for m in memories:
            text.append(f"• [{m.timestamp[:10]}] ", style="dim")
            text.append(f"{m.goal[:38]}... ", style="yellow")
            text.append(f"(Hits: {m.hit_count})\n", style="green")

    return Panel(text, title="🧠 Knowledge Base & Memory Cache", border_style="cyan")


def create_history_table() -> Table:
    table = Table(title="📜 Recent Task History & Execution", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Time", style="dim", width=19)
    table.add_column("Model / Source", style="cyan", width=18)
    table.add_column("Goal / Task Description", style="yellow")

    hist = TaskHistory()
    records = hist.recent(6)
    if not records:
        table.add_row("-", "-", "-", "No tasks executed yet")
    else:
        for r in records:
            status = "[green]✅ PASS[/]" if r.success else "[red]❌ FAIL[/]"
            table.add_row(status, r.timestamp, r.model[:18], r.goal[:65])
    return table


def build_dashboard_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=10),
    )

    layout["main"].split_row(
        Layout(name="left_column", ratio=1),
        Layout(name="right_column", ratio=1),
    )

    layout["left_column"].split_column(
        Layout(name="profiles", ratio=1),
        Layout(name="skills", ratio=1),
    )

    layout["right_column"].split_column(
        Layout(name="stats", ratio=1),
        Layout(name="memory", ratio=1),
    )

    # Populate panels
    layout["header"].update(create_header_panel())
    layout["profiles"].update(create_profiles_table())
    layout["skills"].update(create_skills_table())
    layout["stats"].update(create_stats_table())
    layout["memory"].update(create_memory_panel())
    layout["footer"].update(create_history_table())

    return layout


def render_dashboard():
    """Renders the dashboard snapshot once."""
    layout = build_dashboard_layout()
    console.print(layout)


def run_live_dashboard(refresh_seconds: float = 2.0, max_iterations: Optional[int] = None):
    """Runs a live auto-updating dashboard stream."""
    console.clear()
    iteration = 0
    with Live(build_dashboard_layout(), console=console, refresh_per_second=2, screen=True) as live:
        while True:
            try:
                live.update(build_dashboard_layout())
                time.sleep(refresh_seconds)
                iteration += 1
                if max_iterations is not None and iteration >= max_iterations:
                    break
            except KeyboardInterrupt:
                break
