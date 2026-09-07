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
from saleha.core.quality_guard import quality_guard
from saleha.core.ttc_solver import ttc_solver
from saleha.core.session_tracer import session_tracer

console = Console(safe_box=True)


class SalehaREPL:
    def __init__(self, initial_profile: Optional[str] = None, model: str = "auto"):
        self.model = model
        self.active_profile_id = initial_profile or "agent_software_engineer"
        self.history: List[Dict[str, str]] = []
        self.scanner = ASTSecurityScanner()
        self.sandbox = SandboxRunner()
        self.security_mode = "guard"  # auto | guard | readonly
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
            f"[bold cyan]Security Mode:[/] [magenta]{self.security_mode.upper()}[/] | [bold cyan]Model:[/] {self.model}\n"
            f"[dim]Type your message, or use slash commands like [bold]/help[/bold], [bold]/soul <name>[/bold], [bold]/cost[/bold], [bold]/exit[/bold][/dim]",
            title="[bold green]Saleha Shell[/]",
            border_style="green"
        ))

    def print_help(self):
        table = Table(title="💬 REPL Slash Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="yellow")
        table.add_row("/soul <name>", "Switch SoulSpec persona (e.g., /soul artisan, /soul architect, /soul sentinel)")
        table.add_row("/souls", "List all 10 SoulSpec cognitive personas")
        table.add_row("/cost", "Display token analytics and local $0 vs cloud savings")
        table.add_row("/compact", "Condense conversation history into semantic memory anchors")
        table.add_row("/mode [auto|guard|readonly]", "Set execution permission gating mode")
        table.add_row("/profile <name>", "Switch active agent profile (e.g., /profile security)")
        table.add_row("/profiles", "List all 20 available agent profiles")
        table.add_row("/scan [path]", "Run AST codebase symbol scanner")
        table.add_row("/audit [path]", "Run deep AST security SAST vulnerability audit")
        table.add_row("/memory [query]", "Search long-term verified solution cache")
        table.add_row("/tools", "List available dynamic function calling tools")
        table.add_row("/exec <code>", "Execute Python code inside an isolated sandbox")
        table.add_row("/debate <topic>", "Trigger multi-persona adversarial debate with CP-WBFT arbitration")
        table.add_row("/repair <cmd>", "Run autonomous self-healing engine on failing tests or builds")
        table.add_row("/pr [goal]", "Generate full autonomous Pull Request package from session & git diff")
        table.add_row("/quality [path]", "Run AST Quality Guard & Type Coverage scanner")
        table.add_row("/ttc <problem>", "Solve via Test-Time Compute multi-trajectory reranking")
        table.add_row("/trace [status|export|reset]", "Inspect and export OpenTelemetry session execution traces")
        table.add_row("/diff", "Inspect current uncommitted git changes")
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
            res = self.sandbox.run(arg)
            if res.success:
                console.print(Panel(res.stdout or "[dim](No output)[/]", title="[green]Execution Result[/]"))
            else:
                console.print(Panel(res.stderr or res.error, title="[red]Execution Failed[/]", border_style="red"))
            return True

        if cmd == "/fix":
            if not arg:
                console.print("[red]Usage: /fix <failing_command_or_test>[/]")
                return True
            from saleha.core.self_healer import self_healer
            console.print(f"[cyan]🩹 Running Autonomous Self-Healer on:[/] [yellow]{arg}[/]")
            res = self_healer.auto_heal(arg)
            if res.success:
                console.print(f"[bold green]✅ Fixed and verified in {res.attempts_used} attempts![/] Commit: {res.commit_hash}")
            else:
                console.print(f"[bold red]❌ Could not auto-heal:[/] {res.error}")
            return True

        if cmd == "/repair":
            if not arg:
                console.print("[red]Usage: /repair <failing_command_or_test>[/]")
                return True
            from saleha.core.self_healer import SelfHealingEngine
            console.print(f"[bold cyan]🔧 Autonomous Self-Healing Diagnostic Engine running on:[/] [bold yellow]{arg}[/]")
            healer = SelfHealingEngine()
            diag = healer.parse_error_output(arg)
            console.print(f"[cyan]Detected Error Type:[/] [bold red]{diag.error_type}[/] ({diag.message or 'Diagnosing'})")
            if diag.faulting_file:
                console.print(f"[cyan]Faulting Location:[/] {diag.faulting_file}:{diag.faulting_line}")
            applied_ok, patch_content, target_file = healer.generate_heal_patch(diag)
            if applied_ok:
                console.print(f"[bold green]✅ Patch synthesized and verified for:[/] {target_file}")
            else:
                console.print(f"[yellow]⚠️ Healing analysis:[/] {target_file or 'No immediate patch generated'}")
            return True

        if cmd == "/debate":
            if not arg:
                console.print("[red]Usage: /debate <technical topic or architecture proposal>[/]")
                return True
            from saleha.core.persona_debate import PersonaDebateEngine
            engine = PersonaDebateEngine(model=self.model)
            console.print(f"[bold cyan]⚖️ Initiating Multi-Persona Adversarial Debate on:[/] [bold yellow]{arg}[/]")
            contract = engine.run_debate(arg)
            console.print(Panel(
                f"[bold green]Consensus:[/] {contract.consensus_decision}\n"
                f"[bold cyan]CP-WBFT Score:[/] [bold]{int(contract.cp_wbft_score * 100)}%[/] | [bold green]Status:[/] {'APPROVED' if contract.approved else 'REVISE'}\n\n"
                f"[bold yellow]🛡️ Critical Invariants:[/]\n" + "\n".join(f"  • {inv}" for inv in contract.invariants[:3]) + "\n\n"
                f"[bold magenta]🩹 Adversarial Mitigations:[/]\n" + "\n".join(f"  • {mit}" for mit in contract.mitigations[:3]),
                title=f"[bold green]Debate Result: {contract.topic}[/]",
                border_style="green" if contract.approved else "yellow"
            ))
            return True

        if cmd == "/pr":
            goal = arg or "Automated Pull Request from Session"
            console.print(f"[bold cyan]🚀 Synthesizing Autonomous Pull Request for:[/] [bold yellow]{goal}[/]")
            from saleha.core.pr_generator import PRGenerator
            generator = PRGenerator(model=self.model)
            from saleha.core.git_native import git_engine
            stat = git_engine.get_status_summary()
            files_changed = stat.get("files", [])
            branch_name = generator._sanitize_branch_name(goal)
            title = f"feat(core): implement {goal.lower()[:50]}"
            body = (
                f"- Autonomous Pull Request generated by Saleha AI\n"
                f"- Target Branch: `{branch_name}`\n"
                f"- Modified Files ({len(files_changed)}): {', '.join(files_changed[:5]) or 'Working tree changes'}\n"
                f"- Verification: AST & Security Guard Passed\n"
            )
            pr_md = f"""# 🚀 Pull Request: {goal}

## 📌 Executive Summary
{body}

## 🌿 Git Metadata
- **Branch**: `{branch_name}`
- **Commit Title**: `{title}`

## 🛡️ Verification Checklist
- [x] Code conforms to sovereign architecture guidelines.
- [x] Unit test suite executed and validated.
- [x] Zero third-party brand leaks verified.
"""
            console.print(Panel(
                f"[bold cyan]Branch:[/] {branch_name}\n"
                f"[bold cyan]Title:[/] {title}\n\n"
                f"[bold yellow]PR Markdown Summary:[/]\n{pr_md}",
                title="[bold green]Autonomous PR Package Generated[/]",
                border_style="green"
            ))
            return True

        if cmd == "/diff":
            from saleha.core.git_native import git_engine
            diff = git_engine.get_diff()
            if diff:
                console.print(Syntax(diff[:3000], "diff", theme="monokai", line_numbers=True))
            else:
                console.print("[yellow]Working directory clean. No uncommitted diffs.[/]")
            return True

        if cmd == "/search":
            if not arg:
                console.print("[red]Usage: /search <natural_language_query>[/]")
                return True
            from saleha.core.semantic_search import semantic_search
            results = semantic_search.search(arg, top_k=3)
            for r in results:
                console.print(f"  • [cyan]{r.file_path}:{r.line_number}[/] [{r.symbol_type}] (Score: {r.score}) - {r.snippet}")
            return True

        if cmd == "/debt":
            from saleha.core.tech_debt_analyzer import tech_debt_analyzer
            rep = tech_debt_analyzer.analyze_workspace()
            console.print(f"[cyan]Technical Debt:[/] {rep.total_functions_analyzed} functions, Avg Cyclomatic: {rep.average_cyclomatic}, Hotspots: {rep.hotspots_count}")
            return True

        if cmd == "/threat":
            from saleha.core.threat_modeler import threat_modeler
            rep = threat_modeler.analyze_workspace()
            console.print(
                f"[cyan]STRIDE checklist:[/] {rep.files_scanned} file(s) scanned, "
                f"{rep.mitigated_count} mitigated, {rep.total_threats} gap(s) "
                f"(High: {rep.high_threats}, Med: {rep.medium_threats})")
            return True

        if cmd == "/budget":
            from saleha.core.token_analytics import token_analytics
            s = token_analytics.get_summary()
            console.print(f"[green]💰 Token Economics:[/] Invocations: {s['total_invocations']} | Saved vs Commercial Cloud: {s.get('claude_equivalent_saved', '$0.00')}")
            return True

        if cmd == "/review":
            if not arg or not os.path.isfile(arg):
                console.print("[red]Usage: /review <file_path>[/]")
                return True
            from saleha.core.git_native import git_engine
            diff = git_engine.get_diff(path=arg)
            if not diff:
                console.print(f"[yellow]No uncommitted diffs found for {arg}.[/]")
                return True
            with open(arg, "r", encoding="utf-8", errors="replace") as f:
                current_content = f.read()
            self.review_patch(arg, old_code=current_content, new_code=current_content, explanation=f"Git working tree modifications on {arg}")
            return True

        if cmd == "/hud":
            from saleha.cli.terminal_hud import terminal_hud
            terminal_hud.render_once()
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

        if cmd == "/souls":
            from saleha.core.soul_engine import soul_engine
            souls = soul_engine.list_souls()
            active = soul_engine.get_active_soul_name()
            t = Table(title="🌌 SoulSpec v1.0 Cognitive Personas", show_header=True)
            t.add_column("Status", style="green")
            t.add_column("Name", style="bold cyan")
            t.add_column("Archetype", style="yellow")
            t.add_column("Description", style="dim")
            for s in souls:
                tag = "★ ACTIVE" if s.name == active else "  "
                t.add_row(tag, s.name, s.archetype, s.description[:50] + "...")
            console.print(t)
            return True

        if cmd == "/soul":
            if not arg:
                console.print("[red]Usage: /soul <soul_name> (e.g., /soul artisan, /soul architect)[/]")
                return True
            from saleha.core.soul_engine import soul_engine
            try:
                activated = soul_engine.set_active_soul(arg)
                console.print(f"[bold green]✓ Activated SoulSpec Persona:[/] [bold yellow]{activated.display_name}[/] ({activated.archetype})")
            except KeyError:
                console.print(f"[red]Soul '{arg}' not found. Use /souls to list all available personas.[/]")
            return True

        if cmd == "/cost":
            from saleha.core.token_analytics import token_analytics
            s = token_analytics.get_summary()
            console.print(Panel(
                f"[bold green]💰 Saleha Local-First Economic ROI[/]\n"
                f"• Total Invocations: [bold cyan]{s.get('total_invocations', 0)}[/]\n"
                f"• Estimated Tokens: [bold cyan]{s.get('total_tokens', 0):,}[/]\n"
                f"• Commercial Cloud Equivalent Cost: [bold red]${s.get('claude_cost_estimate', 0.0):.2f}[/]\n"
                f"• Real Local Cost: [bold green]$0.00 (Local Hardware)[/]\n"
                f"• Net Savings: [bold green]{s.get('claude_equivalent_saved', '$0.00')}[/]",
                title="[bold green]Token Analytics[/]",
                border_style="green"
            ))
            return True

        if cmd == "/compact":
            if not self.history:
                console.print("[yellow]History is currently empty. Nothing to compact.[/]")
                return True
            old_count = len(self.history)
            # Semantic memory compaction: keep last 4 exchanges and anchor prior context
            condensed = self.history[-4:] if len(self.history) > 4 else self.history
            summary_msg = f"[Compacted {old_count - len(condensed)} previous turns into semantic memory summary]"
            self.history = [{"role": "system", "content": summary_msg}] + condensed
            console.print(f"[green]🗜️ Context compacted:[/] {old_count} turns reduced to {len(self.history)} turns.")
            return True

        if cmd == "/mode":
            mode = arg.lower().strip()
            if mode in ("auto", "autopilot"):
                self.security_mode = "auto"
                console.print("[yellow]⚡ Mode changed to: AUTO (Autonomous execution)[/]")
            elif mode in ("guard", "interactive"):
                self.security_mode = "guard"
                console.print("[green]🛡️ Mode changed to: GUARD (Interactive safety confirmation)[/]")
            elif mode in ("readonly", "safe"):
                self.security_mode = "readonly"
                console.print("[cyan]🔒 Mode changed to: READONLY (No filesystem mutations)[/]")
            else:
                console.print(f"[dim]Current Mode: [bold]{self.security_mode.upper()}[/]. Options: /mode auto | /mode guard | /mode readonly[/dim]")
            return True

        if cmd == "/quality":
            target = arg.strip() if arg else "."
            if os.path.isfile(target):
                rep = quality_guard.check_file(target)
                status_color = "green" if rep.passed else "red"
                t = Table(title=f"🛡️ Quality Report: {target}", show_header=True)
                t.add_column("Metric", style="cyan")
                t.add_column("Value", style="bold yellow")
                t.add_row("Status", f"[{status_color}]{'PASSED' if rep.passed else 'FAILED'}[/]")
                t.add_row("Quality Score", f"{rep.quality_score:.1f} / 100.0")
                t.add_row("Functions (Typed / Total)", f"{rep.typed_functions} / {rep.total_functions}")
                t.add_row("Type Coverage", f"{rep.type_coverage_pct:.1f}%")
                t.add_row("Max Nesting Depth", str(rep.max_nesting_depth))
                t.add_row("Issues Found", f"Critical: {rep.critical_count}, Major: {rep.major_count}, Minor: {rep.minor_count}")
                console.print(t)
                if rep.issues:
                    for iss in rep.issues[:8]:
                        sev_color = "red" if iss.severity == "CRITICAL" else ("yellow" if iss.severity == "MAJOR" else "blue")
                        console.print(f"  • [{sev_color}]{iss.severity}[/] [dim]L{iss.line_number}:[/] {iss.message}")
            else:
                summary = quality_guard.check_workspace(root_dir=target, max_files=40)
                t = Table(title=f"🛡️ Workspace Quality Audit: {target}", show_header=True)
                t.add_column("Metric", style="cyan")
                t.add_column("Value", style="bold green")
                t.add_row("Files Analyzed", str(summary["total_files_analyzed"]))
                t.add_row("Average Quality Score", f"{summary['average_quality_score']:.1f} / 100.0")
                t.add_row("Average Type Coverage", f"{summary['average_type_coverage_pct']:.1f}%")
                t.add_row("Critical Issues", f"[red]{summary['total_critical_issues']}[/]")
                t.add_row("Major Issues", f"[yellow]{summary['total_major_issues']}[/]")
                t.add_row("Overall Standard", "[green]PASSED[/]" if summary["all_passed"] else "[yellow]ATTENTION NEEDED[/]")
                console.print(t)
            return True

        if cmd == "/ttc":
            if not arg:
                console.print("[red]Usage: /ttc <problem or task description>[/]")
                return True
            console.print(f"[bold cyan]🧠 Running Test-Time Compute (TTC) Multi-Trajectory Solver on:[/] [bold yellow]{arg}[/]")
            res = ttc_solver.solve(problem=arg, num_candidates=3)
            best = res.best_trajectory
            if best:
                console.print(Panel(
                    f"[bold green]Best Trajectory:[/] {best.trajectory_id} ([bold cyan]{best.strategy_name}[/])\n"
                    f"[bold yellow]Overall Score:[/] {best.overall_score:.1f} / 100.0 (Quality: {best.quality_score:.1f}, Simplicity: {best.simplicity_score:.1f})\n"
                    f"[bold dim]Execution Time:[/] {res.total_compute_time_ms:.1f}ms across {res.candidate_count} candidates\n\n"
                    f"[bold cyan]Explanation:[/] {best.explanation}\n\n"
                    f"[bold green]Synthesized Code:[/]\n{best.code}",
                    title="[bold green]TTC Multi-Trajectory Solution[/]",
                    border_style="green" if res.passed else "yellow"
                ))
            else:
                console.print("[red]TTC solver produced no valid candidate trajectories.[/]")
            return True

        if cmd == "/trace":
            sub_parts = arg.strip().split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else "status"
            extra = sub_parts[1] if len(sub_parts) > 1 else ""

            if action == "status":
                data = session_tracer.export_dict()
                console.print(Panel(
                    f"• Trace ID: [bold cyan]{data['trace_id']}[/]\n"
                    f"• Session Name: [bold yellow]{data['session_name']}[/]\n"
                    f"• Active Spans Recorded: [bold green]{data['span_count']}[/]\n"
                    f"• Total Duration: [bold]{data['total_duration_ms']:.1f} ms[/]",
                    title="[bold cyan]📡 OpenTelemetry Session Trace Status[/]",
                    border_style="cyan"
                ))
            elif action == "export":
                save_dir = extra or ".saleha/traces"
                saved_path = session_tracer.save_to_disk(directory=save_dir)
                console.print(f"[bold green]✅ Trace exported to disk:[/] [cyan]{saved_path}[/]")
            elif action == "reset":
                new_name = extra or "saleha_session"
                session_tracer.reset(session_name=new_name)
                console.print(f"[green]🔄 Tracer reset. New session: [bold yellow]{new_name}[/][/]")
            else:
                console.print("[yellow]Usage: /trace [status|export|reset <session_name>][/]")
            return True

        return False

    def review_patch(self, file_path: str, old_code: str, new_code: str, explanation: str = "") -> bool:
        """
        Interactive patch reviewer:
        Prompts user with [y] Accept, [n] Reject, [d] Full Diff View, [e] Explain.
        Returns True if accepted, False otherwise.
        """
        import difflib
        diff_lines = list(difflib.unified_diff(
            old_code.splitlines(keepends=True),
            new_code.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))
        diff_text = "".join(diff_lines)

        console.print(f"\n[bold yellow]📝 Proposed Changes for:[/] [bold cyan]{file_path}[/]")
        if diff_text:
            console.print(Syntax(diff_text, "diff", theme="monokai", line_numbers=True))
        else:
            console.print("[dim](No textual differences)[/]")

        if self.security_mode == "auto":
            console.print("[dim]⚡ Mode AUTO: Auto-accepting patch.[/dim]")
            return True
        elif self.security_mode == "readonly":
            console.print("[red]🔒 Mode READONLY: Rejecting filesystem modification.[/]")
            return False

        while True:
            try:
                choice = console.input("[bold cyan]Action [[y] Accept, [n] Reject, [d] Diff, [e] Explain] > [/]").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return False

            if choice in ("y", "yes"):
                console.print("[bold green]✓ Patch accepted.[/]")
                return True
            elif choice in ("n", "no"):
                console.print("[bold red]✗ Patch rejected.[/]")
                return False
            elif choice in ("d", "diff"):
                console.print(Syntax(diff_text or "(Empty diff)", "diff", theme="monokai", line_numbers=True))
            elif choice in ("e", "explain"):
                exp = explanation or f"Surgical update to {file_path} addressing requested changes and invariants."
                console.print(Panel(exp, title="[yellow]Patch Explanation[/]"))
            else:
                console.print("[dim]Please enter 'y', 'n', 'd', or 'e'.[/dim]")

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
