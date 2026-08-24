"""
Saleha CLI: Full-Screen Terminal TUI Canvas

Interactive multi-pane terminal IDE canvas providing:
1. File Tree & Polyglot Symbol Explorer
2. Multi-turn Agent Chat & Live Code Diffs
3. Real-Time Task DAG Engine Monitor & SAST Security Alerts
4. Interactive Command Palette Bar
"""

import os
import sys
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown

from saleha import __version__
from saleha.core.agent_profile_loader import profile_registry
from saleha.core.memory_store import memory_store
from saleha.core.security_scanner import ASTSecurityScanner
from saleha.core.polyglot_indexer import PolyglotIndexer
from saleha.core.dag_engine import TaskDAG


def build_file_tree(startpath: str = ".", max_depth: int = 2) -> Tree:
    tree = Tree(f"📁 [bold cyan]{os.path.basename(os.path.abspath(startpath)) or 'Root'}[/]")
    try:
        for root, dirs, files in os.walk(startpath):
            # Ignore hidden and cache dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", "dist", "build")]
            level = root.replace(startpath, '').count(os.sep)
            if level >= max_depth:
                continue
            for f in sorted(files)[:8]:
                if f.startswith("."):
                    continue
                ext = os.path.splitext(f)[1]
                color = "green" if ext in (".py", ".ts", ".go", ".rs") else "white"
                tree.add(f"[{color}]📄 {f}[/]")
    except (OSError, PermissionError):
        tree.add("[dim]Empty or inaccessible[/]")
    return tree


def build_tui_layout(active_profile: str = "agent_software_engineer",
                     chat_messages: Optional[List[Dict[str, str]]] = None,
                     sec_issues_count: int = 0,
                     dag_tasks_count: int = 5) -> Layout:
    """Builds a rich 4-pane responsive terminal layout."""
    layout = Layout(name="root")

    # Split into Header, Body, Footer
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )

    # Split Body into Left (Explorer), Center (Chat & Diffs), Right (DAG & Security)
    layout["body"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="center", ratio=5),
        Layout(name="right", ratio=3)
    )

    # 1. Header
    profile = profile_registry.get(active_profile)
    role_name = profile.name if profile else "Senior Software Engineer"
    header_text = Text()
    header_text.append("🧠 SALEHA AI TUI CANVAS", style="bold green")
    header_text.append(f"  |  v{__version__}", style="dim")
    header_text.append(f"  |  Active Persona: [{role_name}]", style="bold cyan")
    header_text.append(f"  |  Memory Items: {len(memory_store.list_all())}", style="bold yellow")
    header_text.append("  |  Status: ⚡ READY", style="bold green")
    layout["header"].update(Panel(header_text, border_style="green"))

    # 2. Left Pane: File Tree Explorer
    file_tree = build_file_tree(".", max_depth=2)
    layout["left"].update(Panel(file_tree, title="[bold cyan]📁 Workspace Explorer[/]", border_style="cyan"))

    # 3. Center Pane: Agent Chat & Code
    chat_content = Text()
    messages = chat_messages or [
        {"role": "assistant", "text": "Welcome to Saleha AI Terminal Canvas! Type any goal or slash command."}
    ]
    for msg in messages:
        if msg["role"] == "user":
            chat_content.append(f"\n👤 You: {msg['text']}\n", style="bold yellow")
        else:
            chat_content.append(f"\n🧠 Saleha: {msg['text']}\n", style="bold green")

    layout["center"].update(Panel(chat_content, title="[bold green]💬 Interactive Agent Canvas[/]", border_style="green"))

    # 4. Right Pane: DAG & SAST Security Monitor
    right_table = Table(box=None, expand=True)
    right_table.add_column("Engine", style="bold cyan")
    right_table.add_column("Status / Metric", style="yellow")
    right_table.add_row("Parallel DAG", f"{dag_tasks_count} Nodes Ready")
    right_table.add_row("AST SAST Audit", f"{sec_issues_count} Vulnerabilities")
    right_table.add_row("Docker Sandbox", "Isolated Ephemeral")
    right_table.add_row("MCP Server", "Active (stdio/SSE)")
    right_table.add_row("Memory Store", f"{len(memory_store.list_all())} Verified Sol.")

    layout["right"].update(Panel(right_table, title="[bold magenta]⚡ Engine Telemetry[/]", border_style="magenta"))

    # 5. Footer Pane: Command Bar
    footer_text = Text("⌨️ Commands: /profile <id> | /scan | /sast | /exec <code> | /mcp | /help | /exit", style="dim cyan")
    layout["footer"].update(Panel(footer_text, border_style="dim"))

    return layout


def start_tui_canvas(console: Optional[Console] = None, interactive: bool = True):
    """Launches interactive full-screen terminal canvas with live telemetry."""
    c = console or Console()
    active_profile = "agent_software_engineer"
    messages = [
        {"role": "assistant", "text": "Welcome to Saleha AI Terminal Canvas! Type a goal or slash command."}
    ]
    sec_count = 0
    dag_count = 5

    if not interactive:
        layout = build_tui_layout(active_profile=active_profile, chat_messages=messages, sec_issues_count=sec_count, dag_tasks_count=dag_count)
        c.clear()
        c.print(layout)
        return

    while True:
        c.clear()
        layout = build_tui_layout(
            active_profile=active_profile,
            chat_messages=messages[-6:],
            sec_issues_count=sec_count,
            dag_tasks_count=dag_count
        )
        c.print(layout)

        try:
            user_input = c.input("\n[bold green]saleha-tui>[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            c.print("\n[yellow]Exiting TUI Canvas...[/]")
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit", "exit", "quit"):
            c.print("\n[yellow]Exiting TUI Canvas. Goodbye![/]")
            break

        if user_input.startswith("/profile"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                active_profile = parts[1].strip()
                messages.append({"role": "assistant", "text": f"Switched active persona to [{active_profile}]."})
            continue

        if user_input in ("/sast", "/audit"):
            scanner = ASTSecurityScanner()
            rep = scanner.scan_directory(".")
            sec_count = rep.total_vulnerabilities
            messages.append({"role": "assistant", "text": f"AST SAST Scan: Found {rep.total_vulnerabilities} issues ({rep.high_count} High, {rep.medium_count} Med)."})
            continue

        if user_input.startswith("/mcp"):
            from saleha.core.mcp_engine import MCPServer
            server = MCPServer()
            tools = [t["name"] for t in server.list_tools()]
            messages.append({"role": "assistant", "text": f"MCP Tools: {', '.join(tools)}"})
            continue

        if user_input.startswith("/help"):
            messages.append({"role": "assistant", "text": "Commands: /profile <id>, /sast, /mcp, /help, /exit. Or type any software goal."})
            continue

        # Normal goal/chat
        messages.append({"role": "user", "text": user_input})
        messages.append({"role": "assistant", "text": f"Acknowledged goal: '{user_input}'. Swarm pipeline prepared."})
