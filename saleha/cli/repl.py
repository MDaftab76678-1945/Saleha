"""
Saleha Interactive REPL & Pair-Programming Shell

Provides a rich multi-turn conversational terminal shell with instant persona
switching, AST scanning, security audits, memory search, and sandboxed execution.
"""

import sys
import os
from typing import Optional, List, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax

from saleha import __version__
from saleha.core.agent_profile_loader import profile_registry, ProfileAgent
from saleha.agents.base_agent import BaseAgent
from saleha.core.memory_store import memory_store
from saleha.core.codebase_indexer import CodebaseIndexer
from saleha.core.security_scanner import ASTSecurityScanner
from saleha.core.tool_calling import global_tool_registry
from saleha.core.sandbox_runner import SandboxRunner

console = Console(safe_box=True)


class SalehaREPL:
    def __init__(self, initial_profile: Optional[str] = None, model: str = "auto"):
        self.model = model
        self.active_profile_id = initial_profile or "agent_software_engineer"
        self.history: List[Dict[str, str]] = []
        self.scanner = ASTSecurityScanner()
        self.sandbox = SandboxRunner()
        self._set_agent()

    def _set_agent(self):
        profile = profile_registry.get(self.active_profile_id)
        if profile:
            self.agent = ProfileAgent(profile=profile, model=self.model)
            self.role_title = f"{profile.name} ({profile.id})"
        else:
            self.agent = BaseAgent(role=self.active_profile_id, model=self.model)
            self.role_title = self.active_profile_id

    def print_welcome(self):
        console.print(Panel.fit(
            f"[bold green]🧠 Saleha Interactive Pair-Programming REPL[/] [dim]v{__version__}[/]\n"
            f"[bold cyan]Active Persona:[/] [yellow]{self.role_title}[/]\n"
            f"[bold cyan]Model:[/] {self.model}\n"
            f"[dim]Type your message, or use slash commands like [bold]/help[/bold], [bold]/profile <name>[/bold], [bold]/exit[/bold][/dim]",
            title="[bold green]Saleha Shell[/]",
            border_style="green"
        ))

    def print_help(self):
        table = Table(title="💬 REPL Slash Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="yellow")
        table.add_row("/profile <name>", "Switch active agent persona (e.g., /profile architect, /profile security)")
        table.add_row("/profiles", "List all 20 available agent profiles")
        table.add_row("/scan [path]", "Run AST codebase symbol scanner")
        table.add_row("/audit [path]", "Run deep AST security SAST vulnerability audit")
        table.add_row("/memory [query]", "Search long-term verified solution cache")
        table.add_row("/tools", "List available dynamic function calling tools")
        table.add_row("/exec <code>", "Execute Python code inside an isolated sandbox")
        table.add_row("/clear", "Clear current conversation history")
        table.add_row("/help", "Show this help table")
        table.add_row("/exit or /quit", "Exit the interactive shell")
        console.print(table)

    def handle_slash_command(self, cmd_line: str) -> bool:
        """Returns True if command was handled, False to continue normal chat."""
        parts = cmd_line.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            console.print("[yellow]Goodbye! Happy coding with Saleha.[/]")
            return True

        if cmd == "/help":
            self.print_help()
            return True

        if cmd == "/clear":
            self.history.clear()
            console.print("[green]🧹 Conversation context cleared.[/]")
            return True

        if cmd == "/profiles":
            profiles = profile_registry.list_profiles()
            t = Table(title="🎭 Available Agent Profiles", show_header=True)
            t.add_column("ID", style="cyan")
            t.add_column("Role Name", style="green")
            for p in profiles:
                t.add_row(p.id, p.name)
            console.print(t)
            return True

        if cmd == "/profile":
            if not arg:
                console.print("[red]Usage: /profile <profile_id or role_name>[/]")
                return True
            matched = profile_registry.get(arg) or profile_registry.match_profile_for_task(arg)
            if matched:
                self.active_profile_id = matched.id
                self._set_agent()
                console.print(f"[green]Switched persona to:[/] [bold yellow]{self.role_title}[/]")
            else:
                console.print(f"[red]Profile '{arg}' not found. Type /profiles to list all.[/]")
            return True

        if cmd == "/scan":
            path = arg or "."
            indexer = CodebaseIndexer(root_dir=path)
            indexer.scan()
            summary = indexer.get_summary()
            console.print(f"[green]AST Scan for '{path}':[/] {summary['total_files']} files, {summary['total_classes']} classes, {summary['total_functions']} functions, {summary['total_loc']} LOC.")
            return True

        if cmd == "/audit":
            path = arg or "."
            report = self.scanner.scan_directory(path)
            console.print(f"[green]Security Audit for '{path}':[/] {report.total_vulnerabilities} issues found (High: {report.high_count}, Med: {report.medium_count}, Low: {report.low_count}).")
            for v in report.vulnerabilities[:5]:
                console.print(f"  - [{v.severity}] {v.rule_id} at {v.file_path}:{v.line_number} ({v.description})")
            return True

        if cmd == "/memory":
            if arg:
                results = memory_store.semantic_search(arg, top_k=3)
                if not results:
                    console.print("[yellow]No matching memories found.[/]")
                for entry, score in results:
                    console.print(f"[green]• [{score:.2f}][/] {entry.goal} (tags: {', '.join(entry.tags)})")
            else:
                stats = memory_store.stats()
                console.print(f"[cyan]Memory Store:[/] {stats['total_memories']} solutions cached, {stats['total_hits']} lifetime hits.")
            return True

        if cmd == "/tools":
            registered = global_tool_registry.list_tools()
            console.print(f"[cyan]Registered Tools:[/] {', '.join([t.name for t in registered])}")
            return True

        if cmd == "/exec":
            if not arg:
                console.print("[red]Usage: /exec <python_code>[/]")
                return True
            res = self.sandbox.run_in_sandbox(arg)
            if res.success:
                console.print(f"[green]Output:[/]\n{res.output}")
            else:
                console.print(f"[red]Error:[/]\n{res.error}")
            return True

        if cmd == "/outline":
            if not arg or not os.path.isfile(arg):
                console.print("[red]Usage: /outline <valid_file_path>[/]")
                return True
            try:
                import ast
                with open(arg, "r", encoding="utf-8", errors="replace") as f:
                    tree = ast.parse(f.read(), filename=arg)
                t = Table(title=f"📐 File Outline: {arg}", show_header=True)
                t.add_column("Type", style="cyan")
                t.add_column("Name", style="bold yellow")
                t.add_column("Lines", style="green")
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        t.add_row("class", node.name, f"{node.lineno}-{node.end_lineno}")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        t.add_row("def", node.name, f"{node.lineno}-{node.end_lineno}")
                console.print(t)
            except Exception as ex:
                console.print(f"[red]Outline error: {ex}[/]")
            return True

        if cmd == "/symbols":
            if not arg:
                console.print("[red]Usage: /symbols <symbol_name>[/]")
                return True
            indexer = CodebaseIndexer(root_dir=".")
            indexer.scan()
            matches = indexer.find_symbol(arg.strip())
            if matches:
                console.print(f"[green]Symbol '{arg}' found in:[/]\n" + "\n".join([f"  • {m}" for m in matches]))
            else:
                console.print(f"[yellow]Symbol '{arg}' not found in codebase.[/]")
            return True

        if cmd == "/status":
            from saleha.core.git_native import git_engine
            stat = git_engine.get_status_summary()
            if stat.get("is_repo"):
                dirty_tag = "[red]Dirty[/]" if stat.get("dirty") else "[green]Clean[/]"
                console.print(f"[cyan]Git Branch:[/] {stat.get('branch')} ({dirty_tag})")
                if stat.get("files"):
                    console.print("[yellow]Modified files:[/]\n" + "\n".join([f"  • {f}" for f in stat["files"][:8]]))
            else:
                console.print("[yellow]Not inside a Git repository.[/]")
            return True

        if cmd == "/undo":
            from saleha.core.git_native import git_engine
            res = git_engine.rollback_last_commit(soft=True)
            if res.get("success"):
                console.print(f"[green]✅ {res.get('message')}[/]")
            else:
                console.print(f"[red]❌ Undo failed: {res.get('error')}[/]")
            return True

        return False

    def run(self):
        self.print_welcome()
        while True:
            try:
                user_input = console.input(f"\n[bold green]You[/] ([dim]{self.active_profile_id}[/]) > ").strip()
                if not user_input:
                    continue

                if user_input.startswith("/"):
                    handled = self.handle_slash_command(user_input)
                    if user_input.lower() in ("/exit", "/quit", "/q"):
                        break
                    if handled:
                        continue

                # Normal multi-turn chat (REAL token streaming -- A2)
                self.history.append({"role": "user", "content": user_input})
                context_prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in self.history[-6:]])

                console.print(f"\n[bold yellow]{self.role_title}[/]:", end="")
                streamed_parts = []

                def _on_token(token: str):
                    streamed_parts.append(token)
                    console.print(token, end="")

                resp = self.agent.think_stream(context_prompt, on_token=_on_token)

                if resp.success and resp.content:
                    self.history.append({"role": "assistant", "content": resp.content})
                    console.print()  # newline after streamed tokens
                    if not streamed_parts:
                        # Provider ne stream nahi kiya (fallback) -- poora output render
                        console.print(Markdown(resp.content))
                    else:
                        console.print("[dim]──[/dim]")
                else:
                    console.print()
                    err_msg = getattr(resp, "error_message", "") or getattr(resp, "error", "") or "No response generated."
                    console.print(f"[red]Agent Error:[/] {err_msg}")

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session closed.[/]")
                break


def start_repl(initial_profile: Optional[str] = None, model: str = "auto"):
    repl = SalehaREPL(initial_profile=initial_profile, model=model)
    repl.run()
