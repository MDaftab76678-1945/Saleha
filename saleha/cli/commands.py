"""
Saleha CLI - Advanced Command Line Interface
उद्देश्य: Terminal से Saleha की पूरी ताकत इस्तेमाल करना

Naya kya hai: `saleha stats` aur `saleha history` commands add hue hain,
taaki persistent data dekhne ke liye lambi `python -c "..."` command na
likhni pade.
"""

import click
import sys
import os
import re
import time
import json
import io
import contextlib
from contextlib import redirect_stdout
from saleha import __version__
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(safe_box=True)

# ==============================================================================
# LAZY IMPORTS (PEP 562)
# Pehle ye file top-level par poora codebase import karti thi -- CLI startup
# ~460ms le raha tha. Ab heavy modules sirf tab load hote hain jab koi command
# actually unhe use kare. Function bodies in names ko globals ke through
# resolve karti hain (call-time lookup), isliye `mock.patch("saleha.cli.
# commands.X")` bhi waise hi kaam karta hai -- patch setattr __getattr__ ko
# override kar deta hai.
# ==============================================================================

_LAZY_IMPORT_MAP = {
    # name -> (module, attribute)
    "SmartRouter": ("saleha.core.smart_router", "SmartRouter"),
    "BaseAgent": ("saleha.agents.base_agent", "BaseAgent"),
    "PlannerAgent": ("saleha.agents.planner", "PlannerAgent"),
    "CoderAgent": ("saleha.agents.coder", "CoderAgent"),
    "TesterAgent": ("saleha.agents.tester", "TesterAgent"),
    "DebuggerAgent": ("saleha.agents.debugger", "DebuggerAgent"),
    "SalehaOrchestrator": ("saleha.orchestrator", "SalehaOrchestrator"),
    "ProjectBuilder": ("saleha.core.project_builder", "ProjectBuilder"),
    "TeamOrchestrator": ("saleha.core.team_orchestrator", "TeamOrchestrator"),
    "skill_registry": ("saleha.core.skill_registry", "registry"),
    "load_builtin_skills": ("saleha.core.skill_registry", "load_builtin_skills"),
    "profile_registry": ("saleha.core.agent_profile_loader", "profile_registry"),
    "memory_store": ("saleha.core.memory_store", "memory_store"),
    "CodebaseIndexer": ("saleha.core.codebase_indexer", "CodebaseIndexer"),
    "SmartPatcher": ("saleha.core.codebase_indexer", "SmartPatcher"),
    "DeliberationEngine": ("saleha.core.deliberation_engine", "DeliberationEngine"),
    "global_tool_registry": ("saleha.core.tool_calling", "global_tool_registry"),
    "SandboxRunner": ("saleha.core.sandbox_runner", "SandboxRunner"),
    "DockerSandboxRunner": ("saleha.core.docker_sandbox", "DockerSandboxRunner"),
    "PolyglotIndexer": ("saleha.core.polyglot_indexer", "PolyglotIndexer"),
    "PRGenerator": ("saleha.core.pr_generator", "PRGenerator"),
    "ASTSecurityScanner": ("saleha.core.security_scanner", "ASTSecurityScanner"),
    "TaskDAG": ("saleha.core.dag_engine", "TaskDAG"),
    "TaskNode": ("saleha.core.dag_engine", "TaskNode"),
    "MCPServer": ("saleha.core.mcp_engine", "MCPServer"),
    "PRReviewBot": ("saleha.ci.bot", "PRReviewBot"),
    "hybrid_gateway": ("saleha.core.hybrid_gateway", "gateway"),
    "run_web_studio": ("saleha.server.web_server", "run_web_studio"),
    "start_repl": ("saleha.cli.repl", "start_repl"),
    "start_tui_canvas": ("saleha.cli.tui_canvas", "start_tui_canvas"),
    "render_dashboard": ("saleha.cli.dashboard", "render_dashboard"),
    "run_live_dashboard": ("saleha.cli.dashboard", "run_live_dashboard"),
    "AgentLoop": ("saleha.core.agentic_loop", "AgentLoop"),
}


class _LazySymbol:
    """Module-global proxy jo pehli actual use par real object load karke
    khud ko globals me swap kar deta hai.

    Kyun zaroori tha: PEP 562 module __getattr__ sirf EXTERNAL attribute
    access handle karta hai -- function bodies ke andar global name lookup
    usse nahi guzarta (isliye pehla attempt NameError hua tha). Proxy se
    command bodies bina kisi badlav ke chalti hain, aur mock.patch("saleha.
    cli.commands.X") bhi waise hi kaam karta hai (patch ka setattr proxy ko
    override kar deta hai).
    """
    __slots__ = ("_module_name", "_attr_name", "_resolved")

    def __init__(self, module_name: str, attr_name: str):
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_attr_name", attr_name)
        object.__setattr__(self, "_resolved", None)

    def _resolve(self):
        obj = object.__getattribute__(self, "_resolved")
        if obj is None:
            import importlib
            obj = getattr(
                importlib.import_module(object.__getattribute__(self, "_module_name")),
                object.__getattribute__(self, "_attr_name"),
            )
            object.__setattr__(self, "_resolved", obj)
            globals()[object.__getattribute__(self, "_attr_name")] = obj
        return obj

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._resolve(), name)


for _name, (_module, _attr) in _LAZY_IMPORT_MAP.items():
    globals()[_name] = _LazySymbol(_module, _attr)
del _name, _module, _attr

# ==============================================================================
# CLI GROUP
# ==============================================================================

@click.group()
@click.version_option(version=__version__, prog_name="Saleha")
def cli():
    """
    Saleha - Self-Healing Multi-Agent AI Engineering Framework
    
    Khud se pehle dusron ke liye.
    """
    pass

# ==============================================================================
# RUN COMMAND - Full Self-Healing Pipeline
# ==============================================================================

@cli.command()
@click.argument('goal', required=False)
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--profile', '-p', default=None, help='Agent profile to adopt (e.g. security_engineer, sde)')
@click.option('--max-attempts', default=3, type=click.IntRange(1, 10), help='Maximum self-healing attempts')

@click.option('--verbose', '-v', is_flag=True, help='Show detailed logs')
@click.option('--execute', '-x', is_flag=True, help='Auto-execute generated code')
@click.option('--commit', '-c', is_flag=True, help='Create atomic conventional git commit upon success')
@click.option('--context-dir', '-cd', default=None, type=click.Path(exists=True, file_okay=False),
              help='Pack task-relevant repo context (Aider-style map) into the coder prompt')
@click.option('--tests', '-t', is_flag=True, help='Generate a unittest suite and use REAL test execution in the healing loop')
@click.option('--resume', '-r', is_flag=True, help='Resume the last interrupted session from its checkpoint')
@click.option('--stream', is_flag=True, help='Stream coder tokens live in the terminal')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def run(goal, model, profile, max_attempts, verbose, execute, commit, context_dir, tests, resume, stream, as_json):
    """
    Full self-healing pipeline: Plan -> Code -> Test -> Fix -> Execute
    
    Example: saleha run "Create a REST API"
    Example with profile: saleha run "Implement distributed lock" -p sde
    Example with execution: saleha run -x "Create a function that prints hello"
    Example with git commit: saleha run -c "Build rate limiter"
    Example with repo context: saleha run "Add retry logic" --context-dir ./src
    Example with real tests: saleha run "Build roman numerals converter" --tests
    Resume after crash: saleha run --resume
    """
    from saleha.core.code_executor import CodeExecutor

    if resume and goal:
        raise click.UsageError("--resume ke saath GOAL mat do -- saved session ka goal use hota hai.")
    if not goal and not resume:
        raise click.UsageError("GOAL zaroori hai (ya --resume use karein).")
    if not goal:
        goal = ""  # orchestrator checkpoint se goal utha lega

    orchestrator = SalehaOrchestrator(model=model, max_healing_attempts=max_attempts, profile=profile)

    if as_json:
        with redirect_stdout(io.StringIO()):
            result = orchestrator.execute_task(goal, profile=profile, auto_commit=commit,
                                               context_dir=context_dir, generate_tests=tests,
                                               resume_session=resume)
    else:
        profile_info = f"\n[bold cyan]🎭 Profile:[/] {profile}" if profile else ""
        context_info = f"\n[bold cyan]📦 Repo Context:[/] {context_dir}" if context_dir else ""
        tests_info = "\n[bold cyan]🧪 Real Tests:[/] enabled" if tests else ""
        resume_info = "\n[bold cyan]⏯️ Mode:[/] RESUME last checkpoint" if resume else ""
        console.print(Panel.fit(
            f"[bold cyan]🎯 Goal:[/] {goal or '(from checkpoint)'}\n"
            f"[bold cyan]🤖 Model:[/] {model}"
            f"{profile_info}"
            f"{context_info}"
            f"{tests_info}"
            f"{resume_info}\n"
            f"[bold cyan]🔄 Max Attempts:[/] {max_attempts}",
            title="[bold green]Saleha Orchestrator[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=stream,  # streaming mode me spinner tokens ke sath conflict karta hai
        ) as progress:
            progress.add_task("[cyan]Processing...", total=None)
            _cb = None
            if stream:
                def _cb(token: str):
                    console.print(token, end="")
            result = orchestrator.execute_task(goal, profile=profile, auto_commit=commit,
                                               context_dir=context_dir, generate_tests=tests,
                                               resume_session=resume, on_token=_cb)
            if stream:
                console.print("\n[dim]── stream end ──[/]")

    if as_json:
        payload = {
            "success": result.success,
            "final_code": result.final_code,
            "attempts": result.attempts,
            "profile_used": getattr(result, "profile_used", ""),
            "log": result.log,
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    
    console.print()
    
    if result.success:
        console.print(Panel(
            f"[bold green]✅ SUCCESS[/] in {result.attempts} attempt(s)",
            border_style="green"
        ))
        
        console.print("\n[bold cyan]📝 Generated Code:[/]")
        syntax = Syntax(result.final_code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)
        
        # Auto-execute if requested
        if execute:
            console.print("\n[bold yellow]🚀 Executing Code...[/]")
            executor = CodeExecutor()
            exec_result = executor.execute(result.final_code)
            
            if exec_result.success:
                console.print(Panel(
                    "[bold green]✅ Execution Successful[/]",
                    border_style="green"
                ))
                if exec_result.output:
                    console.print("\n[bold cyan]📤 Output:[/]")
                    console.print(exec_result.output)
            else:
                console.print(Panel(
                    f"[bold red]❌ Execution Failed[/]",
                    border_style="red"
                ))
                if exec_result.error:
                    console.print(f"\n[red]Error:[/] {exec_result.error}")
    else:
        console.print(Panel(
            f"[bold red]❌ FAILED[/] after {result.attempts} attempt(s)",
            border_style="red"
        ))
    
    if verbose:
        console.print("\n[bold yellow]📜 Execution Log:[/]")
        console.print(result.log)

# ==============================================================================
# AGENT COMMAND - Autonomous ReAct Loop with Surgical AST Tools
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--max-steps', default=10, type=click.IntRange(1, 50), help='Maximum agent exploration/patch steps')
@click.option('--allow-write', '-w', is_flag=True, help='Allow the autonomous agent to patch or write files')
@click.option('--root-dir', '-d', default='.', help='Root workspace directory for the agent')
@click.option('--json', 'as_json', is_flag=True, help='Output machine-readable JSON result')
def agent(goal, model, max_steps, allow_write, root_dir, as_json):
    """
    Run an Autonomous ReAct Agent with surgical tools (patch_file, find_symbols, outline, run_code).
    
    Example: saleha agent "Find charge function in app.py and double the rate" -w
    Example read-only: saleha agent "Audit security of authentication routes"
    """
    base_agent = BaseAgent(role="Autonomous Software Engineer", model=model)
    loop = AgentLoop(agent=base_agent, root_dir=root_dir, max_steps=max_steps, allow_write=allow_write)

    if as_json:
        result = loop.run(goal)
        click.echo(json.dumps({
            "success": result.success,
            "final_message": result.final_message,
            "error": result.error,
            "step_count": len(result.steps),
            "steps": [{"step": s.step_no, "action": s.action, "args": s.args_summary, "observation": s.observation} for s in result.steps]
        }, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return

    console.print(Panel.fit(
        f"[bold cyan]🎯 Goal:[/] {goal}\n"
        f"[bold green]Mode:[/] {'Read/Write (Surgical Patch Enabled)' if allow_write else 'Read-Only Safe Mode'}\n"
        f"[bold magenta]Max Steps:[/] {max_steps}",
        title="[bold green]Saleha Autonomous Agent[/]",
        border_style="green"
    ))

    def on_event(ev):
        action = ev.get("action")
        step_no = ev.get("step")
        if action == "think":
            console.print(f"[dim cyan]🧠 Step {step_no} (Reasoning):[/] {ev.get('thought')}")
        elif action == "finish":
            console.print(f"\n[bold green]🏁 Finished:[/] {ev.get('observation')}")
        elif action == "error":
            console.print(f"\n[bold red]❌ Error:[/] {ev.get('observation')}")
        else:
            obs_prev = str(ev.get("observation", ""))[:120].replace("\n", " ")
            console.print(f"[bold yellow]⚡ Step {step_no}:[/] [cyan]{action}[/] -> [white]{obs_prev}[/]")

    result = loop.run(goal, on_event=on_event)
    console.print()

    if result.success:
        console.print(Panel(
            f"[bold green]✅ Task Complete[/]\n\n{result.final_message}",
            title="[bold green]Success[/]",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]❌ Failed[/]\n\n{result.error}",
            title="[bold red]Incomplete[/]",
            border_style="red"
        ))
        raise click.exceptions.Exit(1)

# ==============================================================================
# PLAN COMMAND - Generate Plan Only
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def plan(goal, model, as_json):
    """
    Generate task plan only (no code generation)
    
    Example: saleha plan "Build a web scraper"
    """
    planner = PlannerAgent(model=model)

    if as_json:
        with redirect_stdout(io.StringIO()):
            result = planner.create_plan(goal)
    else:
        console.print(Panel.fit(
            f"[bold cyan]🎯 Goal:[/] {goal}",
            title="[bold green]Saleha Planner[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Planning...", total=None)
            result = planner.create_plan(goal)

    if as_json:
        click.echo(json.dumps({
            "success": result.success,
            "steps": result.steps,
            "recommendation": result.recommendation,
            "error": result.raw_response if not result.success else "",
        }, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    
    console.print()
    
    if result.success:
        console.print(Panel(
            f"[bold green]✅ Plan Generated[/] (Recommendation: {result.recommendation})",
            border_style="green"
        ))
        
        console.print("\n[bold cyan]📋 Plan Steps:[/]")
        for i, step in enumerate(result.steps, 1):
            console.print(f"  [yellow]{i}.[/] {step}")
    else:
        console.print(Panel(
            f"[bold red]❌ Planning Failed[/]",
            border_style="red"
        ))
        console.print(result.raw_response)

# ==============================================================================
# CODE COMMAND - Generate Code Only
# ==============================================================================

@cli.command()
@click.argument('task')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
@click.option('--output', type=click.Path(dir_okay=False), help='Write generated code to a file')
def code(task, model, as_json, output):
    """
    Generate code for a specific task
    
    Example: saleha code "Create a function to sort a list"
    """
    coder = CoderAgent(model=model)
    if as_json:
        with redirect_stdout(io.StringIO()):
            result = coder.generate_code(task)
    else:
        console.print(Panel.fit(
            f"[bold cyan]💻 Task:[/] {task}",
            title="[bold green]Saleha Coder[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Generating code...", total=None)
            result = coder.generate_code(task)

    if as_json:
        saved_to = ""
        if output and result.success:
            validation = TesterAgent().test_code(result.code)
            if validation.passed:
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(result.code + "\n")
                saved_to = output
            else:
                result.success = False
                result.error = f"{validation.error_type}: {validation.error_message}"
        click.echo(json.dumps({
            "success": result.success,
            "code": result.code,
            "error": result.error,
            "attempts": result.attempts,
            "model_used": result.model_used,
            "saved_to": saved_to,
        }, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return
    
    console.print()
    
    if result.success:
        console.print(Panel(
            f"[bold green]✅ Code Generated[/] in {result.attempts} attempt(s)",
            border_style="green"
        ))
        
        console.print("\n[bold cyan]📝 Code:[/]")
        syntax = Syntax(result.code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)
        if output:
            validation = TesterAgent().test_code(result.code)
            if validation.passed:
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(result.code + "\n")
                console.print(f"\n[bold green]✅ Saved generated code to:[/] {output}")
            else:
                console.print(Panel(
                    f"[bold red]❌ Save cancelled[/] - generated code failed validation\n"
                    f"{validation.error_type}: {validation.error_message}",
                    border_style="red"
                ))
    else:
        console.print(Panel(
            f"[bold red]❌ Code Generation Failed[/]",
            border_style="red"
        ))
        console.print(result.error)

# ============================================================================
# ASK COMMAND - One-shot assistant response
# ============================================================================

@cli.command()
@click.argument('question')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def ask(question, model, as_json):
    """Ask Saleha a normal question without starting the interactive shell."""
    agent = BaseAgent(role="Assistant", model=model)
    result = agent.think(question)

    if as_json:
        payload = {
            "success": result.success,
            "content": result.content,
            "error": result.error_message,
            "model_used": result.model_used,
            "response_time": result.response_time,
        }
        click.echo(json.dumps(payload, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return

    if result.success:
        console.print(result.content)
    else:
        console.print(f"[red]Error:[/] {result.error_message}")
        raise click.exceptions.Exit(1)

# ==============================================================================
# TEST COMMAND - Test Code
# ==============================================================================

@cli.command()
@click.argument('code_file', type=click.Path(exists=True))
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def test(code_file, as_json):
    """
    Test code for syntax and security
    
    Example: saleha test my_script.py
    """
    with open(code_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    tester = TesterAgent()
    if as_json:
        result = tester.test_code(code)
    else:
        console.print(Panel.fit(
            f"[bold cyan]🧪 Testing:[/] {code_file}",
            title="[bold green]Saleha Tester[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Testing code...", total=None)
            result = tester.test_code(code)

    if as_json:
        click.echo(json.dumps({
            "passed": result.passed,
            "error_type": result.error_type,
            "error_message": result.error_message,
            "file": code_file,
        }, ensure_ascii=False))
        if not result.passed:
            raise click.exceptions.Exit(1)
        return
    
    console.print()
    
    if result.passed:
        console.print(Panel(
            "[bold green]✅ PASSED[/] - Code is syntactically correct and secure",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]❌ FAILED[/] - {result.error_type}",
            border_style="red"
        ))
        console.print(f"\n[yellow]Reason:[/] {result.error_message}")

# ============================================================================
# DEBUG COMMAND - Diagnose and repair code
# ============================================================================

@cli.command()
@click.argument('code_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('error_log', required=False)
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--save', is_flag=True, help='Overwrite the input file with corrected code')
@click.option('--error-file', type=click.Path(exists=True, dir_okay=False), help='Read the traceback from a file')
@click.option('--output', type=click.Path(dir_okay=False), help='Write corrected code to a different file')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def debug(code_file, error_log, model, save, error_file, output, as_json):
    """
    Diagnose an error and generate corrected code.

    Example: saleha debug app.py "NameError: name 'x' is not defined"
    """
    if bool(error_log) == bool(error_file):
        raise click.UsageError("Provide either ERROR_LOG or --error-file, but not both.")
    if save and output:
        raise click.UsageError("Use either --save or --output, but not both.")

    with open(code_file, 'r', encoding='utf-8') as f:
        code = f.read()
    if error_file:
        with open(error_file, 'r', encoding='utf-8') as f:
            error_log = f.read()

    agent = DebuggerAgent(model=model)
    if as_json:
        result = agent.debug_code("Debug the provided Python code", code, error_log)
    else:
        console.print(Panel.fit(
            f"[bold cyan]🐞 Debugging:[/] {code_file}\n"
            f"[bold cyan]🤖 Model:[/] {model}",
            title="[bold green]Saleha Debugger[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Analyzing error...", total=None)
            result = agent.debug_code("Debug the provided Python code", code, error_log)

    if not result.success:
        if as_json:
            click.echo(json.dumps({
                "success": False,
                "diagnosis": result.diagnosis,
                "fixed_code": result.fixed_code,
                "error": result.error,
                "model_used": result.model_used,
            }, ensure_ascii=False))
            raise click.exceptions.Exit(1)
        console.print(Panel(f"[bold red]❌ Debugging Failed[/]\n{result.error}", border_style="red"))
        return

    destination = code_file if save else output
    if destination:
        validation = TesterAgent().test_code(result.fixed_code)
        if not validation.passed:
            if as_json:
                click.echo(json.dumps({
                    "success": False,
                    "diagnosis": result.diagnosis,
                    "fixed_code": result.fixed_code,
                    "error": f"{validation.error_type}: {validation.error_message}",
                    "model_used": result.model_used,
                }, ensure_ascii=False))
                raise click.exceptions.Exit(1)
            console.print(Panel(
                f"[bold red]❌ Save cancelled[/] - corrected code failed validation\n"
                f"{validation.error_type}: {validation.error_message}",
                border_style="red"
            ))
            return
        with open(destination, 'w', encoding='utf-8') as f:
            f.write(result.fixed_code + "\n")

    if as_json:
        click.echo(json.dumps({
            "success": True,
            "diagnosis": result.diagnosis,
            "fixed_code": result.fixed_code,
            "error": "",
            "model_used": result.model_used,
            "saved_to": destination or "",
        }, ensure_ascii=False))
        return

    console.print(Panel(
        f"[bold green]✅ Diagnosis[/]\n{result.diagnosis or 'No diagnosis returned.'}",
        border_style="green"
    ))
    console.print("\n[bold cyan]📝 Corrected Code:[/]")
    console.print(Syntax(result.fixed_code, "python", theme="monokai", line_numbers=True))

    # Pehle validate+save block yahan DUPLICATE tha -- file do baar likhi
    # jaati thi aur validation bhi do baar chalti thi. Save upar ho chuka hai.
    if destination:
        console.print(f"\n[bold green]✅ Saved corrected code to:[/] {destination}")

# ==============================================================================
# MODELS COMMAND - Show Available Models
# ==============================================================================

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def models(as_json):
    """
    Show all available models and their stats
    """
    router = SmartRouter()

    if as_json:
        payload = {
            "models": {
                name: {
                    "size_gb": profile.size_gb,
                    "speed": profile.speed,
                    "best_for": profile.best_for,
                    "stats": router.get_model_stats(name),
                }
                for name, profile in router.models.items()
            }
        }
        click.echo(json.dumps(payload, ensure_ascii=False))
        return
    
    table = Table(title="🤖 Available Models", show_header=True, header_style="bold magenta")
    table.add_column("Model", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Speed", style="green")
    table.add_column("Best For", style="yellow")
    
    for model_name, profile in router.models.items():
        table.add_row(
            model_name,
            f"{profile.size_gb}GB",
            profile.speed,
            ", ".join(profile.best_for[:3])
        )
    
    console.print(table)
    
    # Show performance stats
    stats = router.get_all_stats()
    
    if any(s["uses"] > 0 for s in stats.values()):
        console.print("\n[bold cyan]📊 Performance Stats:[/]")
        
        stats_table = Table(show_header=True, header_style="bold magenta")
        stats_table.add_column("Model", style="cyan")
        stats_table.add_column("Uses", justify="right")
        stats_table.add_column("Success Rate", justify="right", style="green")
        stats_table.add_column("Avg Time", justify="right", style="yellow")
        
        for model_name, model_stats in stats.items():
            if model_stats["uses"] > 0:
                stats_table.add_row(
                    model_name,
                    str(model_stats["uses"]),
                    f"{model_stats['success_rate']:.1%}",
                    f"{model_stats['avg_time']:.2f}s"
                )
        
        console.print(stats_table)

# ============================================================================
# SKILLS COMMAND - Show registered local skills
# ============================================================================

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def skills(as_json):
    """Show skills registered in Saleha's local skill registry."""
    load_builtin_skills()
    registered = skill_registry.list_skills()

    if not registered:
        if as_json:
            click.echo(json.dumps({"skills": []}, ensure_ascii=False))
            return
        console.print("[yellow]No skills are currently registered.[/]")
        return

    if as_json:
        click.echo(json.dumps({
            "skills": [
                {"name": skill.name, "description": skill.description}
                for skill in registered
            ]
        }, ensure_ascii=False))
        return

    table = Table(title="Available Skills", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="yellow")
    for skill in registered:
        table.add_row(skill.name, skill.description)
    console.print(table)

# ============================================================================
# AGENTS COMMAND - Show loaded dynamic agent profiles
# ============================================================================

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def agents(as_json):
    """Show dynamic agent profiles loaded from saleha/skills/."""
    profile_registry.reload()
    loaded_profiles = profile_registry.list_profiles()

    if not loaded_profiles:
        if as_json:
            click.echo(json.dumps({"profiles": []}, ensure_ascii=False))
            return
        console.print("[yellow]No agent profiles are currently loaded.[/]")
        return

    if as_json:
        click.echo(json.dumps({
            "profiles": [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "goals": p.goals,
                    "tools": p.allowed_tools,
                    "source_file": os.path.basename(p.source_file),
                }
                for p in loaded_profiles
            ]
        }, ensure_ascii=False))
        return

    table = Table(title="🎭 Loaded Agent Profiles", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Role Name", style="green")
    table.add_column("Ver", justify="center", style="dim")
    table.add_column("Goals / Summary", style="yellow")
    table.add_column("File", style="dim")

    for p in sorted(loaded_profiles, key=lambda x: x.id):
        summary = p.goals[0] if p.goals else (p.system_prompt[:50] + "..." if p.system_prompt else "-")
        table.add_row(
            p.id,
            p.name,
            p.version,
            summary[:60],
            os.path.basename(p.source_file),
        )
    console.print(table)

# ==============================================================================
# PROJECT COMMAND - Multi-file Project Builder (Naya)
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
@click.option('--output-dir', type=click.Path(file_okay=False), help='Base directory for the generated project')
def project(goal, model, as_json, output_dir):
    """
    Build a multi-file project (breaks goal into files, generates each)

    Single-file 'run' command ke bajaye ye bade goals ke liye hai jinme
    ek se zyada files chahiye. Har file alag se generate hoti hai aur
    project folder me save hoti hai (~/saleha_projects/<name>/).

    Example: saleha project "A simple command-line calculator"
    """
    builder = ProjectBuilder(model=model, projects_dir=output_dir) if output_dir else ProjectBuilder(model=model)

    if as_json:
        with redirect_stdout(io.StringIO()):
            result = builder.build(goal)
    else:
        console.print(Panel.fit(
            f"[bold cyan]🏗️ Project Goal:[/] {goal}\n"
            f"[bold cyan]🤖 Model:[/] {model}",
            title="[bold green]Saleha Project Builder[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Building project...", total=None)
            result = builder.build(goal)

    if as_json:
        click.echo(json.dumps({
            "success": result.success,
            "project_dir": result.project_dir,
            "files": [
                {
                    "filename": file_result.filename,
                    "tested_ok": file_result.tested_ok,
                    "test_error": file_result.test_error,
                }
                for file_result in result.files
            ],
            "entry_point": result.entry_point,
            "entry_point_ok": result.entry_point_ok,
            "entry_point_error": result.entry_point_error,
            "log": result.log,
        }, ensure_ascii=False))
        if not result.success:
            raise click.exceptions.Exit(1)
        return

    console.print()

    if result.success:
        console.print(Panel(
            f"[bold green]✅ SUCCESS[/] -- {len(result.files)} files created",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[bold yellow]⚠️ Partial/Failed[/] -- kuch files me problem hai, neeche dekho",
            border_style="yellow"
        ))

    console.print(f"\n[bold cyan]📁 Project location:[/] {result.project_dir}\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Note", style="yellow")

    for f in result.files:
        status = "[green]✅[/]" if f.tested_ok else "[red]❌[/]"
        table.add_row(f.filename, status, f.test_error or "-")

    console.print(table)

# ==============================================================================
# TEAM / SWARM COMMAND - Multi-Agent Collaborative Delivery Pipeline
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--output-dir', '-o', type=click.Path(file_okay=False), help='Directory to export all artifacts (PRD, Design, Code, Tests, Security)')
@click.option('--debate', is_flag=True, help='Enable multi-agent debate and consensus refinement')
@click.option('--max-attempts', default=3, type=click.IntRange(1, 10), help='Maximum self-healing attempts')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def team(goal, model, output_dir, debate, max_attempts, as_json):
    """
    Run multi-agent collaborative swarm pipeline:
    PM (PRD) -> Architect (LLD) -> SDE (Code) -> Security (Audit) -> QA (Tests) -> Verifier (Execution)
    
    Example: saleha team "Build an in-memory caching system with TTL"
    Example with debate: saleha team "Build a distributed lock manager" --debate --output-dir ./dist_lock
    """
    orchestrator = TeamOrchestrator(model=model, max_healing_attempts=max_attempts)

    if as_json:
        with redirect_stdout(io.StringIO()):
            result = orchestrator.run_team_workflow(goal=goal, output_dir=output_dir, debate=debate)
    else:
        out_info = f"\n[bold cyan]📁 Output Dir:[/] {output_dir}" if output_dir else ""
        debate_info = "\n[bold yellow]🤝 Mode:[/] Multi-Agent Deliberation & Debate Enabled" if debate else ""
        console.print(Panel.fit(
            f"[bold cyan]🎯 Swarm Goal:[/] {goal}\n"
            f"[bold cyan]🤖 Model:[/] {model}"
            f"{out_info}"
            f"{debate_info}\n"
            f"[bold cyan]👥 Swarm Team:[/] ProductManager ➔ Architect ➔ SDE ➔ Security ➔ QA ➔ Verifier",
            title="[bold green]Saleha Multi-Agent Swarm[/]",
            border_style="green"
        ))
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("[cyan]Collaborating across team...", total=None)
            result = orchestrator.run_team_workflow(goal=goal, output_dir=output_dir, debate=debate)

    if as_json:
        payload = {
            "success": result.success,
            "goal": result.goal,
            "stages_completed": result.stages_completed,
            "prd": result.prd,
            "design": result.design,
            "code": result.code,
            "security_report": result.security_report,
            "test_code": result.test_code,
            "execution_output": result.execution_output,
            "output_dir": result.output_dir,
            "attempts": result.attempts,
            "log": result.log,
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return

    console.print()
    if result.success:
        console.print(Panel(
            f"[bold green]✅ TEAM SWARM SUCCESS[/] -- Completed all {len(result.stages_completed)} stages",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[bold yellow]⚠️ Swarm Finished with Warnings/Failures[/]",
            border_style="yellow"
        ))

    table = Table(title="👥 Swarm Stage Breakdown", show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="cyan")
    table.add_column("Agent Role", style="green")
    table.add_column("Artifact Produced", style="yellow")

    stage_map = [
        ("1. Requirements", "Product Manager", "PRD & User Stories"),
        ("2. Architecture", "Software Designer", "LLD & Domain Contracts"),
        ("3. Implementation", "Senior SDE", "Production Python Code"),
        ("4. Security", "Security Engineer", "Vulnerability & SAST Audit"),
        ("5. QA & Verification", "Test Architect", "Test Suite & Execution Verification"),
    ]
    for stage_name, role_name, artifact in stage_map:
        table.add_row(stage_name, role_name, artifact)
    console.print(table)

    if result.code:
        console.print("\n[bold cyan]💻 Production Code (Preview):[/]")
        syntax = Syntax(result.code[:600] + ("\n# ... (continued)" if len(result.code) > 600 else ""), "python", theme="monokai", line_numbers=True)
        console.print(syntax)

    if result.output_dir:
        console.print(f"\n[bold green]📁 Full Artifact Package Exported To:[/] {result.output_dir}")

# ==============================================================================
# SCAN & REFACTOR COMMANDS - Codebase AST Intelligence & Smart Patching
# ==============================================================================

@cli.command()
@click.argument('directory', default='.', type=click.Path(exists=True, file_okay=False))
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def scan(directory, as_json):
    """Scan and index codebase AST symbols (classes, methods, functions, imports)."""
    indexer = CodebaseIndexer(root_dir=directory)
    indexed = indexer.scan()
    summary = indexer.get_summary()

    if as_json:
        payload = {
            "summary": summary,
            "files": {
                rel_path: {
                    "lines_of_code": f.lines_of_code,
                    "classes": [c.name for c in f.classes.values()],
                    "functions": [fn.name for fn in f.functions.values()],
                    "imports": f.imports,
                    "syntax_error": f.syntax_error,
                }
                for rel_path, f in indexed.items()
            }
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        return

    console.print(Panel.fit(
        f"[bold cyan]📁 Root Directory:[/] {summary['root_dir']}\n"
        f"[bold cyan]📄 Total Python Files:[/] {summary['total_files']}\n"
        f"[bold cyan]📝 Lines of Code:[/] {summary['total_loc']}\n"
        f"[bold cyan]🏛️ Classes Found:[/] {summary['total_classes']}\n"
        f"[bold cyan]⚡ Functions Found:[/] {summary['total_functions']}",
        title="[bold green]Codebase AST Indexer[/]",
        border_style="green"
    ))

    table = Table(title="📄 Indexed Codebase Files", show_header=True, header_style="bold magenta")
    table.add_column("File Path", style="cyan")
    table.add_column("LOC", justify="right", style="dim")
    table.add_column("Classes", style="green")
    table.add_column("Functions", style="yellow")

    for rel_path, f in sorted(indexed.items())[:20]:
        cls_names = ", ".join(list(f.classes.keys())[:3]) or "-"
        fn_names = ", ".join(list(f.functions.keys())[:3]) or "-"
        table.add_row(rel_path, str(f.lines_of_code), cls_names, fn_names)

    if len(indexed) > 20:
        table.add_row("...", "-", f"+ {len(indexed) - 20} more files", "-")

    console.print(table)


@cli.command()
@click.argument('target_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('instruction')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--diff-only', is_flag=True, help='Only display the unified diff without saving changes')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def refactor(target_file, instruction, model, diff_only, as_json):
    """Refactor a Python file surgically using AST analysis and unified diff patching."""
    with open(target_file, "r", encoding="utf-8") as f:
        original_code = f.read()

    coder = CoderAgent(model=model)
    prompt = f"""
Task: Refactor this existing Python file according to the following instruction.
Instruction: {instruction}

Original File Content ({os.path.basename(target_file)}):
```python
{original_code}
```

Requirements:
- Preserve all existing interfaces, classes, and comments unless explicitly asked to modify them.
- Return the full refactored file in a ```python ... ``` block.
"""
    resp = coder.generate_code(task=instruction, plan=prompt)
    if not resp.success or not resp.code:
        if as_json:
            click.echo(json.dumps({"success": False, "error": resp.error or "Coder failed"}, ensure_ascii=True))
        else:
            console.print(f"[red]❌ Refactoring failed:[/] {resp.error}")
        return

    diff = SmartPatcher.create_unified_diff(original_code, resp.code, os.path.basename(target_file))

    if not diff_only:
        patch_result = SmartPatcher.apply_patch(target_file, resp.code)
        if not patch_result["success"]:
            if as_json:
                click.echo(json.dumps(patch_result, ensure_ascii=True))
            else:
                console.print(f"[red]❌ Patch rejected:[/] {patch_result['error']}")
            return

    if as_json:
        click.echo(json.dumps({
            "success": True,
            "file": target_file,
            "diff": diff,
            "modified": not diff_only,
        }, ensure_ascii=True))
        return

    console.print(Panel(
        f"[bold green]✅ Refactoring Complete[/]\nFile: {target_file}",
        border_style="green"
    ))
    if diff:
        console.print("\n[bold cyan]Unified Diff Patch:[/]")
        syntax = Syntax(diff, "diff", theme="monokai")
        console.print(syntax)

# ==============================================================================
# TOOLS & SANDBOX COMMANDS - Dynamic Tool Calling & VirtualEnv Sandbox Runner
# ==============================================================================

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def tools(as_json):
    """List all available dynamic tools and their JSON schemas."""
    registered = global_tool_registry.list_tools()

    if as_json:
        click.echo(json.dumps({
            "tools": global_tool_registry.get_schemas()
        }, ensure_ascii=True))
        return

    table = Table(title="🛠️ Registered Dynamic Agent Tools", show_header=True, header_style="bold magenta")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Parameters", style="green")
    table.add_column("Description", style="yellow")

    for t in registered:
        params_str = ", ".join([f"{p.name}: {p.type}" for p in t.parameters]) or "None"
        table.add_row(t.name, params_str, t.description)

    console.print(table)


@cli.command()
@click.argument('target_file', type=click.Path(exists=True, dir_okay=False))
@click.option('--deps', '-d', default='', help='Third-party packages to install in sandbox (e.g. "pydantic requests")')
@click.option('--timeout', '-t', default=30, type=int, help='Sandbox execution timeout in seconds')
@click.option('--docker', is_flag=True, help='Execute inside isolated Docker container with memory/CPU cgroups')
@click.option('--lang', default='python', help='Language runtime (python, javascript, go)')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def sandbox(target_file, deps, timeout, docker, lang, as_json):
    """Execute a script inside an isolated ephemeral virtual environment or Docker sandbox."""
    with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
        file_code = f.read()

    if docker:
        docker_runner = DockerSandboxRunner()
        with redirect_stdout(io.StringIO()) if as_json else contextlib.nullcontext():
            result = docker_runner.run_code(code=file_code, language=lang, timeout=timeout)
    else:
        dep_list = [d.strip() for d in re.split(r"[\s,]+", deps) if d.strip()]
        runner = SandboxRunner(default_timeout=timeout)
        with redirect_stdout(io.StringIO()) if as_json else contextlib.nullcontext():
            result = runner.run_in_sandbox(
                script_code_or_file=target_file,
                dependencies=dep_list,
                timeout=timeout
            )

    if as_json:
        payload = {
            "success": result.success,
            "exit_code": result.exit_code,
            "execution_time": round(result.execution_time, 3),
            "installed_packages": result.installed_packages,
            "output": result.output,
            "error": result.error,
            "blocked": result.blocked,
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return

    mode_label = "Docker Container" if docker else "VirtualEnv"
    console.print(Panel.fit(
        f"[bold cyan]📄 Target File:[/] {target_file}\n"
        f"[bold cyan]🛡️ Mode:[/] {mode_label} Sandbox\n"
        f"[bold cyan]⏱️ Timeout:[/] {timeout}s",
        title="[bold green]📦 Isolated Sandbox Execution[/]",
        border_style="green"
    ))

    if result.blocked:
        console.print(Panel(f"[bold red]🚫 Execution Blocked:[/] {result.block_reason}", border_style="red"))
        return

    if result.success:
        console.print(Panel(
            f"[bold green]✅ Sandbox Execution Successful[/] in {result.execution_time:.2f}s (Exit code: {result.exit_code})",
            border_style="green"
        ))
        if result.output:
            console.print("\n[bold cyan]📤 Standard Output:[/]")
            console.print(result.output)
    else:
        console.print(Panel(
            f"[bold red]❌ Sandbox Execution Failed[/] in {result.execution_time:.2f}s (Exit code: {result.exit_code})\nError: {result.error}",
            border_style="red"
        ))

# ==============================================================================
# SERVE & PR COMMANDS - Web Studio Server & Autonomous Git PR Agent
# ==============================================================================

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host address to bind')
@click.option('--port', default=8000, type=int, help='Port to listen on')
@click.option('--open/--no-open', 'open_browser', default=True, help='Open in default browser')
def serve(host, port, open_browser):
    """Launch the interactive Saleha Web Studio & REST API Server."""
    console.print(Panel.fit(
        f"[bold cyan]🌐 URL:[/] http://{host}:{port}\n"
        f"[bold cyan]🚀 Web Studio:[/] Active\n"
        f"[bold cyan]📡 REST & SSE API:[/] Enabled\n"
        f"[dim]Press Ctrl+C in terminal to stop server[/]",
        title="[bold green]🧠 Saleha Web Studio[/]",
        border_style="green"
    ))
    run_web_studio(host=host, port=port, open_browser=open_browser)


@cli.command()
@click.argument('goal')
@click.option('--branch', '-b', default=None, help='Custom git branch name')
@click.option('--output-dir', '-o', default=None, type=click.Path(file_okay=False), help='Directory to export PR markdown and artifacts')
@click.option('--debate', is_flag=True, help='Enable multi-agent deliberation debate')
@click.option('--push', is_flag=True, help='Push feature branch to remote origin')
@click.option('--open-remote', is_flag=True, help='Open Pull Request directly on GitHub')
@click.option('--base', default='main', help='Base branch for remote PR')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def pr(goal, branch, output_dir, debate, push, open_remote, base, model, as_json):
    """Autonomously generate git branch, conventional commit, test evidence, and PULL_REQUEST.md."""
    generator = PRGenerator(model=model)

    if as_json:
        with redirect_stdout(io.StringIO()):
            res = generator.generate_pr(
                goal=goal, branch_name=branch, output_dir=output_dir,
                debate=debate, push=push, open_pr=open_remote, base_branch=base
            )
        payload = {
            "success": res.success,
            "branch_name": res.branch_name,
            "commit_title": res.commit_title,
            "commit_body": res.commit_body,
            "pr_markdown": res.pr_markdown,
            "output_dir": res.output_dir,
            "test_passed": res.test_passed,
            "pr_url": res.pr_url,
            "error": res.error
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not res.success:
            raise click.exceptions.Exit(1)
        return

    console.print(Panel.fit(
        f"[bold cyan]🎯 Goal:[/] {goal}\n"
        f"[bold cyan]🌿 Branch:[/] {branch or generator._sanitize_branch_name(goal)}\n"
        f"[bold cyan]📁 Output Dir:[/] {output_dir or 'Console Only'}\n"
        f"[bold cyan]☁️ Remote Push:[/] {'Enabled' if push or open_remote else 'Disabled'}",
        title="[bold green]🚀 Autonomous Git CI/CD & PR Agent[/]",
        border_style="green"
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("[cyan]Deliberating, implementing, testing & generating PR...", total=None)
        res = generator.generate_pr(
            goal=goal, branch_name=branch, output_dir=output_dir,
            debate=debate, push=push, open_pr=open_remote, base_branch=base
        )

    if res.success:
        console.print(Panel(
            f"[bold green]✅ Pull Request Package Ready[/]\n"
            f"[bold cyan]Branch:[/] {res.branch_name}\n"
            f"[bold cyan]Commit:[/] {res.commit_title}\n"
            f"[bold cyan]Remote PR:[/] {res.pr_url or 'Local Only'}",
            border_style="green"
        ))
        if res.output_dir:
            console.print(f"\n[bold green]📁 Exported PULL_REQUEST.md to:[/] {res.output_dir}")
        else:
            console.print("\n[bold cyan]📄 PULL_REQUEST.md Preview:[/]")
            console.print(Markdown(res.pr_markdown[:800] + "\n\n*(Full markdown generated)*"))
    else:
        console.print(Panel(f"[bold red]❌ PR Generation Failed:[/] {res.error}", border_style="red"))

# ==============================================================================
# DOCTOR COMMAND - Diagnostic checklist (Naya -- is session ke real bugs se banaya)
# ==============================================================================

@cli.command()
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def doctor(as_json):
    """
    Saleha ke common problems ko check karta hai -- jaise wo saari cheezein
    jo is session me manually debug karni padi (Ollama band hona, missing
    files, galat spelling wali files, python/python3 na milna).

    Example: saleha doctor
    """
    if not as_json:
        console.print(Panel.fit("[bold green]🩺 Saleha Doctor[/]", border_style="green"))

    checks = []  # (name, ok: bool, detail: str)

    # 1. python/python3 on PATH
    py = shutil_which_check()
    checks.append(("Python interpreter (python/python3)", py is not None,
                    py or "Neither 'python' nor 'python3' found on PATH"))

    # 2. Required core files present with correct names (catches typo-bugs
    #    like 'sefety_patterns.py' that happened earlier in this session)
    core_dir = os.path.join(os.path.dirname(__file__), '..', 'core')
    required_core_files = [
        "code_executor.py", "safety_patterns.py", "stats_tracker.py",
        "task_history.py", "audit_log.py", "smart_router.py", "project_builder.py",
        "model_provider.py", "self_healing.py", "skill_registry.py",
    ]
    for fname in required_core_files:
        path = os.path.join(core_dir, fname)
        checks.append((f"core/{fname} exists", os.path.isfile(path), path))

    # 3. Required agent files present
    agents_dir = os.path.join(os.path.dirname(__file__), '..', 'agents')
    required_agent_files = [
        "base_agent.py", "coder.py", "tester.py", "reviewer.py", "planner.py", "debugger.py"
    ]
    for fname in required_agent_files:
        path = os.path.join(agents_dir, fname)
        checks.append((f"agents/{fname} exists", os.path.isfile(path), path))

    # 4. Ollama reachable
    ollama_ok, ollama_detail = _check_ollama()
    checks.append(("Ollama server reachable", ollama_ok, ollama_detail))

    # 5. Persistent data directory writable
    saleha_home = os.path.join(os.path.expanduser("~"), ".saleha")
    try:
        os.makedirs(saleha_home, exist_ok=True)
        test_file = os.path.join(saleha_home, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        checks.append((f"~/.saleha/ writable", True, saleha_home))
    except Exception as e:
        checks.append((f"~/.saleha/ writable", False, str(e)))

    if as_json:
        failed = sum(1 for _, ok, _ in checks if not ok)
        click.echo(json.dumps({
            "healthy": failed == 0,
            "checks": [
                {"name": name, "ok": ok, "detail": detail}
                for name, ok, detail in checks
            ],
        }, ensure_ascii=False))
        if failed:
            raise click.exceptions.Exit(1)
        return

    # Results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")

    fail_count = 0
    for name, ok, detail in checks:
        status = "[green]✅[/]" if ok else "[red]❌[/]"
        if not ok:
            fail_count += 1
        table.add_row(name, status, detail[:60])

    console.print(table)

    if fail_count == 0:
        console.print("\n[bold green]Sab theek hai![/] 🎉")
    else:
        console.print(f"\n[bold yellow]{fail_count} problem(s) mile.[/] Upar table me detail dekho.")
        raise click.exceptions.Exit(1)


def shutil_which_check():
    import shutil as _shutil
    for candidate in ("python3", "python"):
        if _shutil.which(candidate):
            return candidate
    return None


def _check_ollama():
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return True, f"{len(models)} model(s) available"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, f"Not reachable -- run 'ollama serve' ({e})"

# ==============================================================================
# STATS COMMAND - Show persistent StatsTracker data (Naya)
# ==============================================================================

@cli.command()
@click.option('--task-type', '-t', default='coding', help='Task category to show stats for')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def stats(task_type, as_json):
    """
    Show persistent model performance stats (saved in ~/.saleha/stats.json)

    Ye 'models' command se alag hai -- 'models' SmartRouter ki apni
    router_history.json dikhata hai, ye command orchestrator ke
    stats_tracker.py wali file dikhata hai.

    Example: saleha stats
    Example: saleha stats --task-type coding
    """
    from saleha.core.stats_tracker import StatsTracker

    tracker = StatsTracker()
    bucket = tracker._data.get(task_type, {})

    if not bucket:
        if as_json:
            click.echo(json.dumps({"task_type": task_type, "models": [], "best_model": None}, ensure_ascii=False))
            return
        console.print(f"[yellow]Abhi tak '{task_type}' ke liye koi stats nahi hain.[/]")
        return

    if as_json:
        models = {}
        for model_name in bucket:
            model_stats = tracker.get_model_stats(model_name, task_type)
            models[model_name] = {
                "uses": model_stats.uses,
                "success_rate": model_stats.success_rate,
                "avg_attempts": model_stats.avg_attempts,
                "last_used": model_stats.last_used,
            }
        click.echo(json.dumps({
            "task_type": task_type,
            "models": models,
            "best_model": tracker.best_model_for(task_type=task_type),
        }, ensure_ascii=False))
        return

    table = Table(title=f"📊 Model Stats ({task_type})", show_header=True, header_style="bold magenta")
    table.add_column("Model", style="cyan")
    table.add_column("Uses", justify="right")
    table.add_column("Success Rate", justify="right", style="green")
    table.add_column("Avg Attempts", justify="right", style="yellow")
    table.add_column("Last Used", style="dim")

    for model_name in sorted(bucket, key=lambda m: -bucket[m]["uses"]):
        s = tracker.get_model_stats(model_name, task_type)
        table.add_row(
            model_name,
            str(s.uses),
            f"{s.success_rate}%",
            str(s.avg_attempts),
            s.last_used or "-",
        )

    console.print(table)

    best = tracker.best_model_for(task_type=task_type)
    if best:
        console.print(f"\n[bold green]🏆 Best model for '{task_type}':[/] {best}")

# ============================================================================
# HISTORY COMMAND - Show recent task history (Naya)
# ============================================================================

@cli.command()
@click.option('--limit', '-n', default=10, help='Number of recent tasks to show')
@click.option('--failed-only', is_flag=True, help='Show only failed tasks')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def history(limit, failed_only, as_json):
    """
    Show recent task history (saved in ~/.saleha/history.jsonl)

    Example: saleha history
    Example: saleha history -n 20
    Example: saleha history --failed-only
    """
    from saleha.core.task_history import TaskHistory

    hist = TaskHistory()
    records = hist.failed_tasks() if failed_only else hist.recent(limit)

    if not records:
        if as_json:
            click.echo(json.dumps({"tasks": []}, ensure_ascii=False))
            return
        console.print("[yellow]Abhi tak koi task history nahi hai.[/]")
        return

    if as_json:
        click.echo(json.dumps({
            "tasks": [record.__dict__ for record in records]
        }, ensure_ascii=False))
        return

    table = Table(title="📜 Task History", show_header=True, header_style="bold magenta")
    table.add_column("Status", justify="center")
    table.add_column("Time", style="dim")
    table.add_column("Model", style="cyan")
    table.add_column("Attempts", justify="right")
    table.add_column("Goal", style="yellow")

    for r in records:
        status = "[green]✅[/]" if r.success else "[red]❌[/]"
        table.add_row(status, r.timestamp, r.model, str(r.attempts), r.goal[:60])

    console.print(table)

# ==============================================================================
# AUDIT COMMAND - Show execution audit records
# ==============================================================================

@cli.command()
@click.option('--limit', '-n', default=20, help='Number of recent records to show')
@click.option('--blocked-only', is_flag=True, help='Show only blocked attempts')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def audit(limit, blocked_only, as_json):
    """Show recent code-execution audit records."""
    from saleha.core.audit_log import AuditLog

    audit_log = AuditLog()
    records = audit_log.blocked_entries() if blocked_only else audit_log.recent(limit)
    if not records:
        if as_json:
            click.echo(json.dumps({"records": []}, ensure_ascii=False))
            return
        console.print("[yellow]No audit records found.[/]")
        return

    if as_json:
        click.echo(json.dumps({"records": records}, ensure_ascii=False))
        return

    table = Table(title="Execution Audit Log", show_header=True, header_style="bold magenta")
    table.add_column("Status", justify="center")
    table.add_column("Time", style="dim")
    table.add_column("Executed", justify="center")
    table.add_column("Code Hash", style="cyan")
    table.add_column("Reason", style="yellow")

    for record in records:
        allowed = record.get("allowed", False)
        status = "[green]ALLOWED[/]" if allowed else "[red]BLOCKED[/]"
        table.add_row(
            status,
            record.get("timestamp", "-"),
            "yes" if record.get("executed") else "no",
            record.get("code_hash", "-")[:16],
            record.get("reason", "")[:70] or "-",
        )

    console.print(table)


# ==============================================================================
# SAST COMMAND - Deep AST Security Vulnerability Scanner
# ==============================================================================

@cli.command()
@click.argument('path', default='.', required=False)
@click.option('--severity', '-s', type=click.Choice(['high', 'medium', 'low', 'all'], case_sensitive=False), default='all', help='Filter by minimum severity')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def sast(path, severity, as_json):
    """Deep AST Security SAST scanner for detecting SQL injection, hardcoded secrets, and unsafe execution."""
    scanner = ASTSecurityScanner()
    if os.path.isfile(path):
        vulns = scanner.scan_file(path)
        total_files = 1
    else:
        report = scanner.scan_directory(path)
        vulns = report.vulnerabilities
        total_files = report.total_files_scanned

    # Filter severity
    filtered_vulns = vulns
    if severity.lower() == 'high':
        filtered_vulns = [v for v in filtered_vulns if v.severity == 'HIGH']
    elif severity.lower() == 'medium':
        filtered_vulns = [v for v in filtered_vulns if v.severity in ('HIGH', 'MEDIUM')]

    high_c = sum(1 for v in filtered_vulns if v.severity == 'HIGH')
    med_c = sum(1 for v in filtered_vulns if v.severity == 'MEDIUM')
    low_c = sum(1 for v in filtered_vulns if v.severity == 'LOW')

    if as_json:
        payload = {
            "path": path,
            "total_files": total_files,
            "total_vulnerabilities": len(filtered_vulns),
            "high": high_c,
            "medium": med_c,
            "low": low_c,
            "vulnerabilities": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "file": v.file_path,
                    "line": v.line_number,
                    "snippet": v.code_snippet,
                    "description": v.description,
                    "remediation": v.remediation
                }
                for v in filtered_vulns
            ]
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        return

    console.print(Panel.fit(
        f"[bold cyan]📁 Target Path:[/] {path}\n"
        f"[bold cyan]📄 Files Scanned:[/] {total_files}\n"
        f"[bold cyan]🛡️ Total Issues:[/] {len(filtered_vulns)} "
        f"([red]High: {high_c}[/], [yellow]Med: {med_c}[/], [blue]Low: {low_c}[/])",
        title="[bold green]🛡️ Deep AST Security SAST Scanner[/]",
        border_style="green" if not high_c else "red"
    ))

    if not filtered_vulns:
        console.print("[bold green]✅ Zero security vulnerabilities detected. Codebase is clean![/]")
        return

    table = Table(title="🚨 Security Vulnerability Breakdown", show_header=True, header_style="bold magenta")
    table.add_column("Severity", justify="center")
    table.add_column("Rule ID", style="cyan")
    table.add_column("Location", style="yellow")
    table.add_column("Description & Remediation", style="white")

    for v in filtered_vulns:
        sev_color = "red" if v.severity == "HIGH" else ("yellow" if v.severity == "MEDIUM" else "blue")
        table.add_row(
            f"[{sev_color}]{v.severity}[/]",
            v.rule_id,
            f"{os.path.basename(v.file_path)}:{v.line_number}",
            f"{v.description}\n[dim]Fix: {v.remediation}[/]"
        )

    console.print(table)


# ==============================================================================
# DAG COMMAND - Parallel Directed Acyclic Graph Engine
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--parallel/--no-parallel', default=True, help='Execute independent task batches in parallel')
@click.option('--workers', '-w', default=4, type=int, help='Maximum parallel worker threads')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def dag(goal, parallel, workers, model, as_json):
    """Execute a complex engineering goal using a parallel Directed Acyclic Graph (DAG) of agents."""
    task_dag = TaskDAG.build_default_dag_for_goal(goal=goal, model=model)

    if as_json:
        with redirect_stdout(io.StringIO()):
            res = task_dag.execute_parallel(max_workers=workers if parallel else 1)
        payload = {
            "success": res.success,
            "goal": res.goal,
            "total_tasks": res.total_tasks,
            "completed_tasks": res.completed_tasks,
            "failed_tasks": res.failed_tasks,
            "total_time": res.total_time,
            "mermaid_graph": res.mermaid_graph,
            "tasks": {
                node.id: {
                    "title": node.title,
                    "role_profile": node.role_profile,
                    "status": node.status,
                    "duration": node.duration,
                    "result_preview": node.result[:150] if node.result else "",
                    "error": node.error
                }
                for node in res.nodes.values()
            }
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        if not res.success:
            raise click.exceptions.Exit(1)
        return

    console.print(Panel.fit(
        f"[bold cyan]🎯 DAG Goal:[/] {goal}\n"
        f"[bold cyan]⚡ Mode:[/] {'Parallel Execution (' + str(workers) + ' threads)' if parallel else 'Sequential'}\n"
        f"[bold cyan]📊 Total Nodes:[/] {len(task_dag.nodes)}",
        title="[bold green]⚡ Parallel Multi-Agent Task Graph (DAG)[/]",
        border_style="green"
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("[cyan]Executing DAG nodes in topological order...", total=None)
        res = task_dag.execute_parallel(max_workers=workers if parallel else 1)

    table = Table(title="📊 DAG Node Execution Status", show_header=True, header_style="bold magenta")
    table.add_column("Node ID", style="cyan")
    table.add_column("Task Title", style="white")
    table.add_column("Agent Profile", style="yellow")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Status", justify="center")

    for node in res.nodes.values():
        status = "[green]✅ COMPLETED[/]" if node.status == "COMPLETED" else "[red]❌ FAILED[/]"
        table.add_row(node.id, node.title, node.role_profile, f"{node.duration:.2f}s", status)

    console.print(table)
    console.print(f"\n[bold green]⏱️ Total DAG Execution Time:[/] {res.total_time:.2f}s")


# ==============================================================================
# CHAT & REPL COMMANDS - Interactive Pair-Programming Shell
# ==============================================================================

@cli.command()
@click.option('--profile', '-p', default=None, help='Initial agent profile (e.g. architect, sde, security)')
@click.option('--model', '-m', default='auto', help='Model to use')
def chat(profile, model):
    """Start an interactive pair-programming shell with Saleha agents."""
    start_repl(initial_profile=profile, model=model)


@cli.command()
@click.option('--profile', '-p', default=None, help='Initial agent profile (e.g. architect, sde, security)')
@click.option('--model', '-m', default='auto', help='Model to use')
def repl(profile, model):
    """Alias for 'saleha chat'."""
    start_repl(initial_profile=profile, model=model)

# ==============================================================================
# AGENT COMMAND - Autonomous ReAct Tool-Use Loop (v1.1 keystone)
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--dir', 'root_dir', default='.', type=click.Path(exists=True, file_okay=False),
              help='Repository root the agent operates in')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--max-steps', default=12, type=click.IntRange(1, 40), help='Maximum think-act steps')
@click.option('--write', is_flag=True, help='Allow write_file tool (still gated by SALEHA_APPROVAL)')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable transcript')
def agent(goal, root_dir, model, max_steps, write, as_json):
    """Autonomous agent that thinks, uses tools, and investigates a repo.

    Example: saleha agent "find all API endpoints missing auth checks" --dir ./src
    """
    from saleha.core.agentic_loop import AgentLoop
    from saleha.agents.base_agent import BaseAgent

    console.print(Panel.fit(
        f"[bold cyan]🎯 Goal:[/] {goal}\n"
        f"[bold cyan]📁 Root:[/] {os.path.abspath(root_dir)}\n"
        f"[bold cyan]🔧 Tools:[/] list_dir, read_file, search_repo, run_code"
        f"{', write_file' if write else ''}\n"
        f"[bold cyan]🔁 Max Steps:[/] {max_steps}",
        title="[bold green]🤖 Saleha Autonomous Agent[/]",
        border_style="green"
    ))

    loop = AgentLoop(agent=BaseAgent(role="Agent", model=model),
                     root_dir=root_dir, max_steps=max_steps,
                     allow_write=write)
    result = loop.run(goal, on_event=lambda ev: None if as_json else console.print(
        f"[dim]step {ev.get('step')}[/] [cyan]{ev.get('action')}[/] "
        f"-> {_one_line(ev.get('observation', ''))}"
    ))

    if as_json:
        click.echo(json.dumps({
            "success": result.success,
            "final_message": result.final_message,
            "error": result.error,
            "steps": [
                {"step": s.step, "action": s.action,
                 "args": s.args_preview, "observation": s.observation[:500]}
                for s in result.steps
            ],
        }, ensure_ascii=True))
    else:
        console.print(Panel(
            result.final_message or result.error,
            title="[green]✅ Agent Summary[/]" if result.success else "[red]❌ Agent Stopped[/]",
            border_style="green" if result.success else "red"
        ))
        console.print(f"[dim]{len(result.steps)} step(s) used[/]")
    if not result.success:
        raise click.exceptions.Exit(1)


def _one_line(text: str) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:100] + ("..." if len(text) > 100 else "")


# ==============================================================================
# EDIT COMMAND - Multi-File Surgical Editor (C1)
# ==============================================================================

@cli.command()
@click.argument('goal')
@click.option('--dir', 'root_dir', default='.', type=click.Path(exists=True, file_okay=False),
              help='Target repository root (default: current dir)')
@click.option('--model', '-m', default='auto', help='Model to use')
@click.option('--apply', is_flag=True, help='Actually write changes (default: dry-run plan only)')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable edit plan')
def edit(goal, root_dir, model, apply, as_json):
    """Plan (and optionally apply) multi-file edits across an existing repo.

    Example dry-run:  saleha edit "add retry logic to API calls" --dir ./src
    Example apply:    saleha edit "rename helper.py to utils" --dir . --apply
    """
    from saleha.core.multi_file_editor import MultiFileEditor

    coder = CoderAgent(model=model)
    editor = MultiFileEditor(coder_agent=coder, root_dir=root_dir)

    mode_label = "[bold red]APPLY[/]" if apply else "[bold yellow]DRY-RUN[/]"
    console.print(Panel.fit(
        f"[bold cyan]🎯 Goal:[/] {goal}\n"
        f"[bold cyan]📁 Root:[/] {os.path.abspath(root_dir)}\n"
        f"[bold cyan]⚙️ Mode:[/] {mode_label}",
        title="[bold green]✏️ Saleha Multi-File Editor[/]",
        border_style="green"
    ))

    result = editor.edit(goal, apply=apply)

    if as_json:
        click.echo(json.dumps({
            "success": result.success,
            "applied": result.applied,
            "rolled_back": result.rolled_back,
            "errors": result.errors,
            "edits": [
                {"path": e.path, "action": e.action, "lines": e.lines_changed}
                for e in result.edits
            ],
        }, ensure_ascii=True))
        if not result.success:
            raise click.exceptions.Exit(1)
        return

    if result.edits:
        table = Table(title=f"Edit Plan ({len(result.edits)} file(s))")
        table.add_column("Action", style="yellow")
        table.add_column("Path", style="cyan")
        table.add_column("Lines", justify="right")
        for e in result.edits:
            table.add_row(e.action, e.path, str(e.lines_changed))
        console.print(table)

        # Unified diff previews (existing-file edits ke liye)
        from rich.syntax import Syntax as _Syntax
        for e in result.edits:
            if e.diff:
                console.print(f"\n[bold cyan]📄 Diff: {e.path}[/]")
                console.print(_Syntax(e.diff, "diff", theme="monokai"))

    if result.success and result.applied:
        console.print(f"[green]✅ {len(result.edits)} file(s) written atomically.[/]")
    elif result.success:
        console.print("[yellow]Dry-run only. Re-run with [bold]--apply[/] to write changes.[/]")
    else:
        for err in result.errors[:6]:
            console.print(f"[red]• {err}[/]")
        if result.rolled_back:
            console.print("[red]↩️ Changes rolled back -- disk untouched.[/]")
        raise click.exceptions.Exit(1)

# ==============================================================================
# PROFILE COMMAND - Hardware Telemetry Profiler (v1.6)
# ==============================================================================

@cli.command(name='profile')
@click.option('--watch', '-w', default=0, type=int, help='Live refresh: N seconds tak sample karo')
@click.option('--top', default=5, type=int, help='Top processes to show')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable snapshot')
def profile_cmd(watch, top, as_json):
    """Hardware telemetry: CPU/mem/disk/net + top processes (GPU if nvidia-smi)."""
    from saleha.core.hardware_profiler import get_profiler

    profiler = get_profiler()
    if profiler is None:
        console.print("[red]psutil unavailable -- hardware profiling needs psutil[/]")
        raise click.exceptions.Exit(1)

    snap = profiler.record_window(seconds=watch) if watch > 0 else profiler.snapshot()

    payload = {
        "cpu_percent": snap.cpu_percent,
        "cpu_per_core": snap.cpu_per_core,
        "cpu_freq_mhz": snap.cpu_freq_mhz,
        "mem_used_mb": snap.mem_used_mb,
        "mem_total_mb": snap.mem_total_mb,
        "mem_percent": snap.mem_percent,
        "swap_percent": snap.swap_percent,
        "disk_write_mb_s": snap.disk_write_mb_s,
        "net_recv_kb_s": snap.net_recv_kb_s,
        "gpu": snap.gpu,
        "top_processes": snap.top_processes[:top],
    }
    if as_json:
        import json as _json
        click.echo(_json.dumps(payload, ensure_ascii=True, default=str))
        return

    core_bars = " ".join(
        f"[{'green' if c < 60 else 'yellow' if c < 85 else 'red'}]{int(c):>3}[/]"
        for c in snap.cpu_per_core[:16]
    )
    console.print(Panel(
        f"[bold cyan]CPU:[/] {snap.cpu_percent}%   "
        f"[cyan]Freq:[/] {snap.cpu_freq_mhz or '-'} MHz\n"
        f"Per-core: {core_bars}\n"
        f"[bold cyan]RAM:[/] {snap.mem_used_mb}/{snap.mem_total_mb} MB "
        f"({snap.mem_percent}%)\n"
        f"[bold cyan]Swap:[/] {snap.swap_percent}%   "
        f"[cyan]Disk W:[/] {snap.disk_write_mb_s} MB/s   "
        f"[cyan]Net RX:[/] {snap.net_recv_kb_s} KB/s\n"
        + (f"[magenta]GPU:[/] {snap.gpu['name']} util={snap.gpu['util_percent']}% mem={snap.gpu['mem_used_mb']}MB\n"
           if snap.gpu else "")
        ,
        title="[bold green]🖥️ Saleha Hardware Profile[/]",
        border_style="green"
    ))

    from rich.table import Table
    tp = Table(title=f"Top Processes (self pid={snap.self_pid})")
    tp.add_column("PID", justify="right", style="dim")
    tp.add_column("Name")
    tp.add_column("CPU%", justify="right")
    tp.add_column("MEM%", justify="right")
    for p in snap.top_processes[:top]:
        marker = " ← saleha" if p["pid"] == snap.self_pid else ""
        tp.add_row(str(p["pid"]), str(p.get("name")) + marker,
                   str(p.get("cpu")), str(p.get("mem_pct")))
    console.print(tp)

# ==============================================================================
# METRICS COMMAND - Structured Run Observability (B3)
# ==============================================================================

@cli.command()
@click.option('--tail', '-n', default=10, help='Recent events to show')
@click.option('--json', 'as_json', is_flag=True, help='Machine-readable summary + tail')
def metrics(tail, as_json):
    """Show run success-rate, avg attempts, per-model stats & recent events."""
    from saleha.core.metrics import metrics_tracker

    summary = metrics_tracker.summary()
    recent = metrics_tracker.tail(limit=tail)

    if as_json:
        click.echo(json.dumps({"summary": summary, "recent": recent}, ensure_ascii=True))
        return

    console.print(Panel.fit("[bold green]Saleha Run Metrics[/]", border_style="green"))
    console.print(f"[cyan]Total Runs:[/] {summary['total_runs']}  |  "
                  f"[green]✅ {summary['successful_runs']}[/]  "
                  f"[red]❌ {summary['failed_runs']}[/]")
    console.print(f"[cyan]Success Rate:[/] {summary['success_rate']}%   "
                  f"[cyan]Avg Attempts:[/] {summary['avg_attempts']}   "
                  f"[cyan]Avg Duration:[/] {summary['avg_duration_sec']}s")

    if summary["by_model"]:
        table = Table(title="Per-Model Performance")
        table.add_column("Model", style="cyan")
        table.add_column("Runs", justify="right")
        table.add_column("Wins", justify="right", style="green")
        for model_name, slot in sorted(summary["by_model"].items(),
                                       key=lambda kv: kv[1]["runs"], reverse=True):
            table.add_row(model_name, str(slot["runs"]), str(slot["wins"]))
        console.print(table)

    if recent:
        rt = Table(title=f"Recent Events (last {len(recent)})")
        rt.add_column("Time", style="dim")
        rt.add_column("Event")
        rt.add_column("Detail")
        for e in recent:
            ts = time.strftime("%H:%M:%S", time.localtime(e.get("ts", 0)))
            detail = ""
            if e.get("event") == "run_completed":
                detail = (f"{'✅' if e.get('success') else '❌'} attempts={e.get('attempts')} "
                          f"model={e.get('model')}")
            rt.add_row(ts, str(e.get("event")), detail or "-")
        console.print(rt)

# ==============================================================================
# DASHBOARD / UI COMMAND - Live Operational Terminal Dashboard
# ==============================================================================

@cli.command()
@click.option('--live', is_flag=True, help='Run auto-refreshing live dashboard')
@click.option('--refresh', default=2.0, help='Refresh interval in seconds (for live mode)')
def dashboard(live, refresh):
    """Render the Saleha multi-agent operations dashboard."""
    if live:
        run_live_dashboard(refresh_seconds=refresh)
    else:
        render_dashboard()


@cli.command()
@click.option('--live', is_flag=True, help='Run auto-refreshing live dashboard')
@click.option('--refresh', default=2.0, help='Refresh interval in seconds (for live mode)')
def ui(live, refresh):
    """Alias for 'saleha dashboard'."""
    if live:
        run_live_dashboard(refresh_seconds=refresh)
    else:
        render_dashboard()

# ==============================================================================
# MEMORY COMMAND GROUP - Long-Term Knowledge Base & Solution Cache
# ==============================================================================

@cli.group()
def memory():
    """Manage Saleha persistent solution memory and knowledge base."""
    pass


@memory.command('list')
@click.option('--limit', '-n', default=20, help='Number of memories to show')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def memory_list(limit, as_json):
    """List verified solutions stored in persistent memory."""
    memories = memory_store.list_all(limit=limit)

    if not memories:
        if as_json:
            click.echo(json.dumps({"memories": []}, ensure_ascii=True))
            return
        console.print("[yellow]Persistent memory is currently empty.[/]")
        return

    if as_json:
        click.echo(json.dumps({
            "memories": [
                {
                    "id": m.id,
                    "goal": m.goal,
                    "model": m.model,
                    "tags": m.tags,
                    "timestamp": m.timestamp,
                    "hit_count": m.hit_count,
                    "code_preview": m.code[:100],
                }
                for m in memories
            ]
        }, ensure_ascii=True))
        return

    table = Table(title="🧠 Persistent Knowledge Base", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Hits", justify="right", style="green")
    table.add_column("Timestamp", style="dim")
    table.add_column("Tags", style="yellow")
    table.add_column("Goal / Specification", style="white")

    for m in memories:
        table.add_row(
            m.id,
            str(m.hit_count),
            m.timestamp[:19],
            ", ".join(m.tags[:3]) if m.tags else "-",
            m.goal[:60],
        )
    console.print(table)


@memory.command('search')
@click.argument('query')
@click.option('--semantic', is_flag=True, help='Use TF-IDF Vector Semantic Search')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def memory_search(query, semantic, as_json):
    """Search solutions in memory by keyword, tag, or vector semantic similarity."""
    if semantic:
        raw_results = memory_store.semantic_search(query)
        results = [entry for entry, score in raw_results]
        scores = {entry.id: score for entry, score in raw_results}
    else:
        results = memory_store.search(query)
        scores = {}

    if not results:
        if as_json:
            click.echo(json.dumps({"results": []}, ensure_ascii=True))
            return
        console.print(f"[yellow]No memories matched query '{query}'.[/]")
        return

    if as_json:
        click.echo(json.dumps({
            "query": query,
            "semantic": semantic,
            "results": [
                {
                    "id": m.id,
                    "goal": m.goal,
                    "tags": m.tags,
                    "hit_count": m.hit_count,
                    "score": scores.get(m.id, 1.0),
                    "code": m.code,
                }
                for m in results
            ]
        }, ensure_ascii=True))
        return

    mode_label = " (Semantic Vector Mode)" if semantic else ""
    table = Table(title=f"🔍 Memory Search: '{query}'{mode_label}", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    if semantic:
        table.add_column("Score", justify="right", style="magenta")
    table.add_column("Hits", justify="right", style="green")
    table.add_column("Goal", style="white")
    table.add_column("Tags", style="yellow")

    for m in results:
        row = [m.id]
        if semantic:
            row.append(f"{scores.get(m.id, 0.0):.2f}")
        row.extend([str(m.hit_count), m.goal[:60], ", ".join(m.tags[:3])])
        table.add_row(*row)
    console.print(table)


@memory.command('clear')
@click.option('--yes', '-y', is_flag=True, help='Confirm wiping memory without prompt')
def memory_clear(yes):
    """Clear all verified solutions from persistent memory."""
    if not yes:
        if not click.confirm("Are you sure you want to clear all persistent solution memories?"):
            console.print("[yellow]Cancelled.[/]")
            return
    memory_store.clear()
    console.print("[green]✅ Persistent memory cleared successfully.[/]")


@memory.command('stats')
@click.option('--json', 'as_json', is_flag=True, help='Print a machine-readable JSON response')
def memory_stats(as_json):
    """Show memory store statistics."""
    stats = memory_store.stats()
    if as_json:
        click.echo(json.dumps(stats, ensure_ascii=True))
        return
    console.print(Panel.fit(
        f"[bold cyan]📦 Total Memories:[/] {stats['total_memories']}\n"
        f"[bold cyan]🎯 Total Cache Hits:[/] {stats['total_hits']}\n"
        f"[bold cyan]📁 File Path:[/] {stats['storage_path']}",
        title="[bold green]Memory Store Statistics[/]",
        border_style="green"
    ))

# STATUS COMMAND - Show System Status
# ==============================================================================

@cli.command()
def status():
    """
    Show Saleha system status
    """
    console.print(Panel.fit(
        "[bold green]Saleha System Status[/]",
        border_style="green"
    ))
    
    # Check Ollama connection
    # Pehle hardcoded "qwen3.5:0.8b" health-check prompt fire hota tha -- ab
    # lightweight /api/tags probe (koi LLM call nahi, koi hardcoded model nahi).
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/version", timeout=2) as resp:
            ollama_alive = resp.status == 200
    except OSError:
        ollama_alive = False

    if ollama_alive:
        from saleha.core.smart_router import get_installed_ollama_models
        live_models = get_installed_ollama_models()
        if live_models:
            console.print(f"[green]✅ Ollama:[/] Connected ({len(live_models)} model(s) installed)")
            console.print(f"[green]   Models:[/] {', '.join(sorted(live_models)[:8])}")
        else:
            console.print("[green]✅ Ollama:[/] Connected (koi model installed nahi mila)")
    else:
        console.print("[red]❌ Ollama:[/] Not reachable at http://localhost:11434")
    
    # Show router stats
    router = SmartRouter()
    stats = router.get_all_stats()
    total_uses = sum(s["uses"] for s in stats.values())
    
    console.print(f"\n[cyan]📊 Total Tasks Processed:[/] {total_uses}")
    console.print(f"[cyan]🧠 Models Available:[/] {len(router.models)}")

# ==============================================================================
# INTERACTIVE COMMAND - Interactive Shell
# ==============================================================================

@cli.command()
@click.option('--model', '-m', default='auto', help='Model to use')
def interactive(model):
    """
    Start interactive Saleha shell
    
    Example: saleha interactive
    """
    console.print(Panel.fit(
        "[bold green]Saleha Interactive Shell[/]\n"
        "Type 'exit' or 'quit' to leave\n"
        "Type 'help' for commands\n"
        "Type 'code: <task>' for coding tasks",
        border_style="green"
    ))
    
    orchestrator = SalehaOrchestrator(model=model)
    
    while True:
        try:
            user_input = console.input("\n[bold cyan]Saleha>[/] ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit']:
                console.print("[yellow]Goodbye![/]")
                break
            
            if user_input.lower() == 'help':
                console.print("\n[bold]Commands:[/]")
                console.print("  [cyan]code: <task>[/] - Coding task")
                console.print("  [cyan]<question>[/] - Normal chat")
                console.print("  [cyan]exit[/] - Exit shell")
                console.print("  [cyan]help[/] - Show this help\n")
                continue
            
            # Check if it's a coding task
            is_coding = user_input.lower().startswith('code:')
            
            if is_coding:
                # Full pipeline for coding
                task = user_input[5:].strip()
                result = orchestrator.execute_task(task)
                
                if result.success:
                    console.print(f"\n[green]✅ Success![/] ({result.attempts} attempts)")
                    console.print("\n[bold]Code:[/]")
                    syntax = Syntax(result.final_code, "python", theme="monokai", line_numbers=True)
                    console.print(syntax)
                else:
                    console.print(f"\n[red]❌ Failed![/] ({result.attempts} attempts)")
            else:
                # Normal chat - direct LLM response
                agent = BaseAgent(role="Assistant", model=model)
                response = agent.think(user_input)
                
                if response.success:
                    console.print(f"\n[green]Saleha:[/] {response.content}")
                else:
                    console.print(f"\n[red]Error:[/] {response.error_message}")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted![/]")
            break
        except EOFError:
            break

# ==============================================================================
# MCP, CI/CD REVIEW, & TUI CANVAS COMMANDS
# ==============================================================================

@cli.group()
def mcp():
    """Model Context Protocol (MCP) server & client commands."""
    pass


@mcp.command(name='serve')
@click.option('--stdio', is_flag=True, default=True, help='Run MCP server over standard I/O (default)')
def mcp_serve(stdio):
    """Start standard Model Context Protocol (MCP) server for Claude Desktop, Cursor, etc."""
    server = MCPServer()
    server.run_stdio_loop()


@mcp.command(name='tools')
@click.option('--json', 'as_json', is_flag=True, help='Print as JSON array')
def mcp_tools(as_json):
    """List all tools exposed by the Saleha MCP Server."""
    server = MCPServer()
    tools = server.list_tools()
    if as_json:
        click.echo(json.dumps({"tools": tools}, ensure_ascii=True, indent=2))
        return

    table = Table(title="🔌 Saleha MCP Server Tools", box=None)
    table.add_column("Tool Name", style="bold cyan")
    table.add_column("Description", style="yellow")
    for t in tools:
        table.add_row(t["name"], t["description"])
    console.print(table)


@cli.group()
def ci():
    """Autonomous CI/CD and Pull Request review commands."""
    pass


@ci.command(name='review')
@click.argument('target_dir', default='.', type=click.Path(exists=True))
@click.option('--pr', 'pr_number', default=None, type=int, help='Pull request number')
@click.option('--output', '-o', default=None, type=click.Path(), help='Export markdown review report to file')
@click.option('--json', 'as_json', is_flag=True, help='Output review report as JSON')
def ci_review(target_dir, pr_number, output, as_json):
    """Run autonomous AST SAST security audit and code quality review."""
    bot = PRReviewBot()
    report = bot.review_path(target_dir, pr_number=pr_number)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report.markdown_review)

    if as_json:
        payload = {
            "status": report.status,
            "quality_score": report.quality_score,
            "total_files": report.total_files,
            "total_loc": report.total_loc,
            "high_vulnerabilities": report.security_report.high_count,
            "medium_vulnerabilities": report.security_report.medium_count,
            "low_vulnerabilities": report.security_report.low_count,
            "suggested_actions": report.suggested_actions,
            "markdown_review": report.markdown_review
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        if report.status == "CHANGES_REQUESTED":
            raise click.exceptions.Exit(1)
        return

    console.print(Panel(
        f"[bold green]Status:[/] {report.status}\n"
        f"[bold cyan]Quality Score:[/] {report.quality_score}/100\n"
        f"[bold cyan]Files Scanned:[/] {report.total_files} ({report.total_loc} LOC)\n"
        f"[bold yellow]Security Issues:[/] {report.security_report.total_vulnerabilities} ({report.security_report.high_count} High)",
        title="[bold green]🤖 Saleha CI/CD Autonomous Code Review[/]",
        border_style="green" if report.status == "APPROVED" else "red"
    ))
    console.print(Markdown(report.markdown_review[:1200] + "\n\n*(Full report generated)*"))


@cli.command()
def tui():
    """Launch full-screen interactive Terminal TUI Canvas IDE."""
    start_tui_canvas(console)


@cli.command()
def canvas():
    """Alias for 'saleha tui'."""
    start_tui_canvas(console)


@cli.command()
@click.option('--hard', is_flag=True, help='Hard reset instead of soft revert')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def undo(hard, as_json):
    """
    Safely undo/rollback the last Saleha Git commit (Aider-style).
    
    Example: saleha undo
    Example hard reset: saleha undo --hard
    """
    from saleha.core.git_native import git_engine
    result = git_engine.rollback_last_commit(soft=not hard)
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=True))
        return

    if result.get("success"):
        console.print(Panel(
            f"[bold green]✅ Success:[/] {result.get('message')}\n"
            f"[dim]Reverted:[/] {result.get('reverted_commit')}",
            title="[bold green]🌿 Saleha Git Undo[/]",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]❌ Undo Failed:[/] {result.get('error')}",
            title="[bold red]🌿 Saleha Git Undo[/]",
            border_style="red"
        ))


@cli.command()
@click.argument('url')
@click.option('--selector', '-s', multiple=True, help='DOM selectors to verify (e.g. "#app", ".navbar")')
@click.option('--screenshot', '-p', default=None, help='File path to save screenshot')
@click.option('--timeout', '-t', default=10, help='Page load timeout in seconds')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def browser(url, selector, screenshot, timeout, as_json):
    """
    Automated Headless Browser Testing & Verification (Playwright).
    
    Example: saleha browser http://localhost:8000
    Example with DOM check: saleha browser http://localhost:3000 -s "#root" -s "button"
    Example with screenshot: saleha browser http://localhost:8000 --screenshot ./app.png
    """
    from saleha.core.browser_runner import browser_runner
    
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Navigating to {url}..."),
        console=console,
    ) as progress:
        progress.add_task("browser", total=None)
        res = browser_runner.navigate(
            url=url,
            expected_selectors=list(selector),
            capture_screenshot=bool(screenshot),
            screenshot_path=screenshot,
            timeout=timeout
        )

    if as_json:
        click.echo(json.dumps({
            "success": res.success,
            "url": res.url,
            "status_code": res.status_code,
            "title": res.title,
            "console_errors": res.console_errors,
            "screenshot_path": res.screenshot_path,
            "dom_elements_found": res.dom_elements_found,
            "load_time": res.load_time,
            "backend": res.backend,
            "error": res.error
        }, ensure_ascii=True))
        return

    status_color = "green" if res.success else "red"
    dom_summary = "\n".join([f"  • {k}: {'✅ Found' if v else '❌ Missing'}" for k, v in res.dom_elements_found.items()]) if res.dom_elements_found else "  • None requested"
    error_summary = "\n".join([f"  • {e}" for e in res.console_errors]) if res.console_errors else "  • None detected"

    console.print(Panel(
        f"[bold cyan]URL:[/] {res.url}\n"
        f"[bold cyan]Status Code:[/] [{status_color}]{res.status_code}[/]\n"
        f"[bold cyan]Title:[/] {res.title or 'N/A'}\n"
        f"[bold cyan]Backend:[/] {res.backend}\n"
        f"[bold cyan]Load Time:[/] {res.load_time}s\n"
        f"[bold yellow]DOM Elements:[/]\n{dom_summary}\n"
        f"[bold red]Console Errors:[/]\n{error_summary}" +
        (f"\n[bold green]Screenshot:[/] {res.screenshot_path}" if res.screenshot_path else ""),
        title=f"[{status_color}]🌐 Saleha Headless Browser Verification[/]",
        border_style=status_color
    ))


@cli.command(name='exec')
@click.argument('filepath')
@click.option('--lang', '-l', default=None, help='Explicit language (python, javascript, typescript, go, java, rust)')
@click.option('--timeout', '-t', default=15, help='Execution timeout in seconds')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def exec_code(filepath, lang, timeout, as_json):
    """
    Execute code in multi-language sandbox with pre-execution AST SAST security gates.
    
    Supports: Python (.py), Node.js (.js), TypeScript (.ts), Go (.go), Java (.java), Rust (.rs)
    
    Example: saleha exec app.py
    Example JS: saleha exec server.js
    Example Go: saleha exec main.go
    """
    from saleha.core.polyglot_executor import polyglot_executor
    
    if not os.path.isfile(filepath):
        console.print(f"[bold red]Error:[/] File '{filepath}' not found.")
        raise click.exceptions.Exit(1)

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()

    polyglot_executor.timeout = timeout
    res = polyglot_executor.execute(code, language=lang, filename=os.path.basename(filepath))

    if as_json:
        click.echo(json.dumps({
            "success": res.success,
            "language": res.language,
            "exit_code": res.exit_code,
            "output": res.output,
            "error": res.error,
            "blocked": res.blocked,
            "block_reason": res.block_reason,
            "execution_time": res.execution_time
        }, ensure_ascii=True))
        return

    if res.blocked:
        console.print(Panel(
            f"[bold red]🚫 Execution Blocked by SAST Gate[/]\n\n"
            f"[yellow]Reason:[/] {res.block_reason}",
            title="[bold red]Security Block[/]",
            border_style="red"
        ))
        raise click.exceptions.Exit(1)

    status_color = "green" if res.success else "red"
    output_content = res.output.strip() or "(No stdout output)"
    error_content = f"\n[bold red]Stderr/Error:[/]\n{res.error.strip()}" if res.error.strip() else ""

    console.print(Panel(
        f"[bold cyan]Language:[/] {res.language}\n"
        f"[bold cyan]Exit Code:[/] [{status_color}]{res.exit_code}[/]\n"
        f"[bold cyan]Time:[/] {res.execution_time}s\n\n"
        f"[bold green]Stdout Output:[/]\n{output_content}"
        f"{error_content}",
        title=f"[{status_color}]⚡ Saleha Polyglot Execution ({res.language})[/]",
        border_style=status_color
    ))


@cli.group(name='git')
def git_group():
    """Git-Native operations, conventional commits, and pre-commit security hooks."""
    pass


@git_group.command(name='hook')
@click.argument('action', type=click.Choice(['install', 'uninstall', 'status']))
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def git_hook_cmd(action, as_json):
    """
    Manage Git pre-commit AST SAST security gates.
    
    Example install: saleha git hook install
    Example uninstall: saleha git hook uninstall
    """
    from saleha.core.git_hooks import hook_manager
    
    if action == 'install':
        res = hook_manager.install_pre_commit()
    elif action == 'uninstall':
        res = hook_manager.uninstall_pre_commit()
    else:
        git_dir = os.path.join(os.path.abspath("."), ".git", "hooks", "pre-commit")
        installed = os.path.isfile(git_dir)
        res = {"installed": installed, "hook_path": git_dir if installed else None}

    if as_json:
        click.echo(json.dumps(res, ensure_ascii=True))
        return

    if action == 'status':
        status_txt = "[bold green]Active (Installed)[/]" if res.get("installed") else "[yellow]Not Installed[/]"
        console.print(f"🛡️ Pre-Commit SAST Hook: {status_txt}")
        return

    if res.get("success"):
        console.print(f"[bold green]✅ {res.get('message')}[/]")
    else:
        console.print(f"[bold red]❌ {res.get('error')}[/]")


@git_group.command(name='status')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def git_status_cmd(as_json):
    """View current Git repository status and branch."""
    from saleha.core.git_native import git_engine
    status = git_engine.get_status_summary()
    if as_json:
        click.echo(json.dumps(status, ensure_ascii=True))
        return

    if not status.get("is_repo"):
        console.print("[bold red]Not a Git repository.[/]")
        return

    dirty_txt = "[bold red]Dirty (Uncommitted Changes)[/]" if status.get("dirty") else "[bold green]Clean[/]"
    console.print(Panel(
        f"[bold cyan]Branch:[/] {status.get('branch')}\n"
        f"[bold cyan]Working Tree:[/] {dirty_txt}\n"
        f"[bold cyan]Uncommitted Files:[/] {status.get('dirty_count')}\n" +
        "\n".join([f"  • {f}" for f in status.get("files", [])]),
        title="[bold green]🌿 Saleha Git Status[/]",
        border_style="green"
    ))


# ==============================================================================
# ENCRYPTED SECRET VAULT COMMANDS
# ==============================================================================

@cli.group(name='vault')
def vault_group():
    """Encrypted Secret & Credential Vault (PBKDF2-HMAC-SHA256)."""
    pass


@vault_group.command(name='set')
@click.argument('key')
@click.argument('value')
@click.option('--desc', default='', help='Description for this secret')
def vault_set_cmd(key, value, desc):
    """Store or update an encrypted secret in the vault."""
    from saleha.core.vault import vault
    ok = vault.set_secret(key, value, description=desc)
    if ok:
        console.print(f"[bold green]🔐 Secret '{key}' stored securely in encrypted vault.[/]")
    else:
        console.print(f"[bold red]❌ Failed to store secret '{key}'.[/]")


@vault_group.command(name='get')
@click.argument('key')
def vault_get_cmd(key):
    """Retrieve and decrypt a secret value from the vault."""
    from saleha.core.vault import vault
    val = vault.get_secret(key)
    if val is not None:
        click.echo(val)
    else:
        console.print(f"[bold red]Secret '{key}' not found in vault or environment.[/]")
        raise click.exceptions.Exit(1)


@vault_group.command(name='list')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def vault_list_cmd(as_json):
    """List all stored secrets with masked previews and timestamps."""
    from saleha.core.vault import vault
    secrets_list = vault.list_secrets()

    if as_json:
        payload = [{
            "key": s.key,
            "preview": s.preview,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "description": s.description
        } for s in secrets_list]
        click.echo(json.dumps(payload, ensure_ascii=True))
        return

    if not secrets_list:
        console.print("[yellow]Vault is empty. Use 'saleha vault set <KEY> <VALUE>' to add secrets.[/]")
        return

    from rich.table import Table
    table = Table(title="🔐 Saleha Encrypted Secret Vault", border_style="cyan")
    table.add_column("Secret Key", style="bold cyan")
    table.add_column("Masked Preview", style="yellow")
    table.add_column("Description", style="dim")
    table.add_column("Last Updated", style="green")

    for s in secrets_list:
        table.add_row(s.key, s.preview, s.description or "-", s.updated_at)

    console.print(table)


@vault_group.command(name='delete')
@click.argument('key')
def vault_delete_cmd(key):
    """Delete a secret from the vault."""
    from saleha.core.vault import vault
    ok = vault.delete_secret(key)
    if ok:
        console.print(f"[bold green]🗑️ Secret '{key}' deleted from vault.[/]")
    else:
        console.print(f"[bold red]Secret '{key}' was not found in vault.[/]")


@vault_group.command(name='export')
def vault_export_cmd():
    """Inject all vault secrets into the current environment session."""
    from saleha.core.vault import vault
    exported = vault.export_to_env()
    console.print(f"[bold green]✅ Exported {len(exported)} secret(s) to environment.[/]")


# ==============================================================================
# BENCHMARK EVALUATOR COMMAND
# ==============================================================================

@cli.command(name='benchmark')
@click.option('--model', '-m', default='auto', help='Ollama model to benchmark')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of test cases')
@click.option('--dry-run', is_flag=True, help='Simulate benchmark run without LLM calls')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def benchmark_cmd(model, limit, dry_run, as_json):
    """
    Benchmark local Ollama models on HumanEval-style coding challenges.
    
    Example: saleha benchmark -m qwen2.5-coder:1.5b
    Example dry run: saleha benchmark --dry-run
    """
    from saleha.core.evaluator import evaluator
    
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Benchmarking model '{model}'..."),
        console=console,
    ) as progress:
        progress.add_task("bench", total=None)
        score = evaluator.run_benchmark(model=model, limit=limit, dry_run=dry_run)

    if as_json:
        click.echo(json.dumps({
            "model": score.model,
            "total_tasks": score.total_tasks,
            "passed_tasks": score.passed_tasks,
            "pass_rate": score.pass_rate,
            "avg_latency_sec": score.avg_latency_sec,
            "task_results": score.task_results
        }, ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title=f"📊 Saleha Benchmark Report — Model: {score.model}", border_style="green")
    table.add_column("Task ID", style="bold cyan")
    table.add_column("Difficulty", style="dim")
    table.add_column("Passed", style="bold")
    table.add_column("Latency", style="yellow")

    for res in score.task_results:
        pass_txt = "[green]✅ PASS[/]" if res["passed"] else "[red]❌ FAIL[/]"
        table.add_row(res["task_id"], res["difficulty"], pass_txt, f"{res['latency_sec']}s")

    console.print(table)
    console.print(Panel(
        f"[bold cyan]Model:[/] {score.model}\n"
        f"[bold cyan]Pass@1 Rate:[/] [bold green]{score.pass_rate}%[/] ({score.passed_tasks}/{score.total_tasks} passed)\n"
        f"[bold cyan]Average Latency:[/] {score.avg_latency_sec}s per task",
        title="[bold green]🏆 Benchmark Summary[/]",
        border_style="green"
    ))


# ==============================================================================
# 6-HORIZON DEEP CAPABILITY COMMANDS
# ==============================================================================

@cli.command(name='graph')
@click.argument('path', default='.')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def graph_cmd(path, as_json):
    """Build and inspect cross-file AST symbol call dependency graph."""
    from saleha.core.dependency_graph import dependency_graph
    summary = dependency_graph.build_graph(root_dir=path)

    if as_json:
        click.echo(json.dumps(summary, ensure_ascii=True))
        return

    console.print(Panel(
        f"[bold cyan]Root Path:[/] {dependency_graph.root_dir}\n"
        f"[bold cyan]Files Indexed:[/] {summary['total_files']}\n"
        f"[bold cyan]Symbol Definitions:[/] {summary['total_definitions']}\n"
        f"[bold cyan]Cross-File Call References:[/] {summary['total_references']}",
        title="[bold green]🌲 Saleha Codebase Dependency Graph[/]",
        border_style="green"
    ))


@cli.command(name='callers')
@click.argument('symbol')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def callers_cmd(symbol, as_json):
    """Find all code callers referencing a specific function, class, or method."""
    from saleha.core.dependency_graph import dependency_graph
    if not dependency_graph.files_indexed:
        dependency_graph.build_graph()
    callers = dependency_graph.find_callers(symbol)

    if as_json:
        payload = [{
            "symbol": c.symbol_called,
            "file": c.caller_file,
            "line": c.caller_line,
            "context": c.caller_context
        } for c in callers]
        click.echo(json.dumps(payload, ensure_ascii=True))
        return

    if not callers:
        console.print(f"[yellow]No callers found for symbol '{symbol}'.[/]")
        return

    from rich.table import Table
    table = Table(title=f"🌲 Callers of '{symbol}'", border_style="cyan")
    table.add_column("Caller File", style="bold cyan")
    table.add_column("Line", style="yellow")
    table.add_column("Context", style="green")

    for c in callers:
        table.add_row(c.caller_file, str(c.caller_line), c.caller_context)

    console.print(table)


@cli.command(name='doc')
@click.argument('package')
@click.argument('symbol', required=False, default=None)
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def doc_cmd(package, symbol, as_json):
    """Look up verified API signatures from local offline documentation cache."""
    from saleha.core.doc_researcher import doc_researcher
    from dataclasses import asdict
    
    if symbol:
        sig = doc_researcher.lookup(package, symbol)
        if as_json:
            click.echo(json.dumps(asdict(sig) if sig else None, ensure_ascii=True))
            return
        if sig:
            console.print(Panel(
                f"[bold cyan]Package:[/] {sig.package}\n"
                f"[bold cyan]Symbol:[/] {sig.symbol}\n"
                f"[bold yellow]Signature:[/] `{sig.signature}`\n\n"
                f"[bold green]Description:[/]\n{sig.docstring}\n\n"
                f"[bold dim]Example:[/]\n{sig.example}",
                title=f"[bold green]📖 API Reference: {sig.package}.{sig.symbol}[/]",
                border_style="green"
            ))
        else:
            console.print(f"[yellow]No documentation found for '{package}.{symbol}'.[/]")
    else:
        results = doc_researcher.search_docs(package)
        if as_json:
            click.echo(json.dumps([asdict(r) for r in results], ensure_ascii=True))
            return
        if not results:
            console.print(f"[yellow]No documentation found matching '{package}'.[/]")
            return
        from rich.table import Table
        table = Table(title=f"📖 Documentation for '{package}'", border_style="cyan")
        table.add_column("Package", style="bold cyan")
        table.add_column("Symbol", style="bold yellow")
        table.add_column("Description", style="dim")
        for r in results:
            table.add_row(r.package, r.symbol, r.docstring[:60] + "...")
        console.print(table)


@cli.command(name='plugins')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def plugins_cmd(as_json):
    """List loaded dynamic plugins and lifecycle event hooks."""
    from saleha.core.plugin_loader import plugin_loader
    plugins = plugin_loader.list_plugins()

    if as_json:
        payload = [{
            "name": p.name,
            "version": p.version,
            "description": p.description,
            "file": p.file_path,
            "hooks": p.hooks_registered
        } for p in plugins]
        click.echo(json.dumps(payload, ensure_ascii=True))
        return

    if not plugins:
        console.print(Panel(
            "[yellow]No external plugins loaded.[/]\n\n"
            "💡 You can drop custom Python plugins into [bold cyan]~/.saleha/plugins/[/] or [bold cyan].saleha/plugins/[/]\n"
            "Supported hooks: [dim]on_task_start, on_code_generated, on_test_complete, on_commit[/]",
            title="[bold green]🔌 Saleha Plugin Registry[/]",
            border_style="green"
        ))
        return

    from rich.table import Table
    table = Table(title="🔌 Loaded Plugins", border_style="green")
    table.add_column("Plugin Name", style="bold cyan")
    table.add_column("Version", style="dim")
    table.add_column("Description", style="yellow")
    table.add_column("Hooks", style="green")

    for p in plugins:
        table.add_row(p.name, p.version, p.description, ", ".join(p.hooks_registered) or "None")

    console.print(table)


@cli.command(name='stream')
@click.argument('prompt')
@click.option('--model', '-m', default='auto', help='Model to stream from')
def stream_cmd(prompt, model):
    """Stream generated tokens in real-time with typewriter syntax highlighting."""
    from saleha.core.streaming_ui import streaming_ui
    streaming_ui.stream_to_terminal(model=model, prompt=prompt, title="Saleha Stream")


# ==============================================================================
# APEX FRONTIER COMMANDS (REPL, PR REVIEW, VOICE, SWE-BENCH)
# ==============================================================================

@cli.command(name='debug-repl')
def repl_cmd():
    """Start an interactive stateful Python AI REPL & live variable debugger.

    (Pehle ye 'repl' naam se registered tha, jisne 'saleha repl --profile'
    chat alias ko silently overwrite kar diya tha -- isliye rename kiya gaya.)
    """
    from saleha.core.debugger_repl import repl
    repl.interactive_loop()


@cli.command(name='pr-review')
@click.argument('base_branch', default='main')
@click.option('--output-file', '-o', default=None, help='Save review markdown report to file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def pr_review_cmd(base_branch, output_file, as_json):
    """Analyze Git PR diff, run SAST security scan, and generate review comments."""
    from saleha.core.pr_reviewer import pr_reviewer
    diff_text = pr_reviewer.get_git_diff(base_branch=base_branch)
    report = pr_reviewer.review_diff(diff_text, pr_title=f"Branch diff against {base_branch}")

    if as_json:
        click.echo(json.dumps({
            "summary": report.summary,
            "risk_level": report.risk_level,
            "files_analyzed": report.files_analyzed,
            "security_findings": report.security_findings,
            "recommendations": report.recommendations,
            "merge_decision": report.merge_decision
        }, ensure_ascii=True))
        return

    console.print(Markdown(report.markdown_report))

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report.markdown_report)
        console.print(f"\n[bold green]💾 Review saved to {output_file}[/]")


@cli.command(name='voice')
@click.argument('prompt', required=False, default=None)
@click.option('--audio', '-a', default=None, type=click.Path(exists=True),
              help='Audio file (wav/mp3/flac) -- faster-whisper se LOCAL transcription hogi')
@click.option('--whisper-model', default='base', type=click.Choice(['tiny', 'base', 'small', 'medium']),
              help='Whisper model size (default: base)')
@click.option('--speak', '-s', is_flag=True, help='Result summary ko loudly bolo (pyttsx3 TTS)')
@click.option('--model', '-m', default='auto', help='Model to execute task with')
def voice_cmd(prompt, audio, whisper_model, speak, model):
    """Voice task: audio -> text -> autonomous pipeline -> (optional) spoken result.

    Text mode:   saleha voice "create a login endpoint"
    Audio mode:  saleha voice --audio note.wav
    Speak back:  saleha voice --audio note.wav --speak

    Requires [voice] extra for audio: pip install saleha[voice]
    """
    from saleha.core.voice_assistant import voice_assistant

    if audio:
        from saleha.core.speech import WhisperSTT
        if not WhisperSTT.available():
            console.print("[red]❌ faster-whisper installed nahi hai.[/]")
            console.print("[dim]Install: pip install saleha[voice][/]")
            raise click.exceptions.Exit(1)
        console.print(f"[cyan]🎧 Transcribing[/] {os.path.basename(audio)} (whisper:{whisper_model})...")
        stt = WhisperSTT(model_size=whisper_model)
        tr = stt.transcribe(audio)
        if not tr.success or not tr.text:
            console.print(f"[red]❌ Transcription failed:[/] {tr.error or 'empty audio'}")
            raise click.exceptions.Exit(1)
        prompt = tr.text
        console.print(f"[green]✅ Heard ({tr.language}, {tr.duration_sec}s):[/] "
                      f"[cyan]\"{prompt}\"[/]")
    elif not prompt:
        console.print("[yellow]PROMPT ya --audio/<file> dijiye.[/] "
                      "[dim]Example: saleha voice \"build rate limiter\" ya --audio note.wav[/]")
        raise click.exceptions.Exit(2)

    console.print(f"[bold green]🎙️ Voice Assistant — Executing:[/] [cyan]\"{prompt}\"[/]")
    res = voice_assistant.process_voice_prompt(prompt, auto_execute=True)
    if res.success:
        console.print(Panel(
            res.execution_result or "Task completed successfully.",
            title="[bold green]✅ Voice Task Output[/]",
            border_style="green"
        ))
        if speak:
            from saleha.core.speech import PyttsxTTS
            tts = PyttsxTTS()
            if not tts.available():
                console.print("[yellow]⚠️ TTS ke liye pyttsx3 chahiye: pip install saleha[voice][/]")
            else:
                spoken = (res.execution_result or "Task completed")[:280]
                ok = tts.speak(spoken)
                console.print("[green]🔊 Spoken.[/]" if ok else "[red]🔊 TTS failed.[/]")
    else:
        console.print(f"[bold red]❌ Task failed:[/] {res.error}")


@cli.command(name='swe-bench')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of task instances')
@click.option('--dry-run', is_flag=True, help='Simulate evaluation without execution')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def swe_bench_cmd(limit, dry_run, as_json):
    """Run SWE-Bench verified evaluation harness on repository-level bug fixing instances."""
    from saleha.core.swe_bench_harness import swe_bench
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Running SWE-Bench verification suite..."),
        console=console,
    ) as progress:
        progress.add_task("swe", total=None)
        report = swe_bench.run_evaluation(limit=limit, dry_run=dry_run)

    if as_json:
        click.echo(json.dumps({
            "total_instances": report.total_instances,
            "resolved_instances": report.resolved_instances,
            "pass_rate": report.pass_rate,
            "avg_latency_sec": report.avg_latency_sec,
            "results": report.results
        }, ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title="🧪 SWE-Bench Verification Report", border_style="cyan")
    table.add_column("Instance ID", style="bold cyan")
    table.add_column("Repository", style="dim")
    table.add_column("Resolved", style="bold")
    table.add_column("Latency", style="yellow")

    for r in report.results:
        res_txt = "[green]✅ RESOLVED[/]" if r["resolved"] else "[red]❌ UNRESOLVED[/]"
        table.add_row(r["instance_id"], r["repo"], res_txt, f"{r['latency_sec']}s")

    console.print(table)
    console.print(Panel(
        f"[bold cyan]Pass Rate:[/] [bold green]{report.pass_rate}%[/] ({report.resolved_instances}/{report.total_instances} resolved)\n"
        f"[bold cyan]Average Time:[/] {report.avg_latency_sec}s per instance",
        title="[bold green]🏆 SWE-Bench Summary[/]",
        border_style="green"
    ))


# ==============================================================================
# SALEHA HARNESS COMMANDS (DEEPSEEK-STYLE EVALUATION HARNESS)
# ==============================================================================

@cli.group(name='harness')
def harness_group():
    """Industrial-Strength Model Evaluation Framework (DeepSeek Harness standard)."""
    pass


@harness_group.command(name='list')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def harness_list_cmd(as_json):
    """List available benchmark datasets in the harness catalog."""
    from saleha.harness.benchmarks import BenchmarkCatalog
    catalogs = BenchmarkCatalog.list_available_benchmarks()

    if as_json:
        click.echo(json.dumps(catalogs, ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title="📚 Saleha Harness Benchmark Datasets", border_style="cyan")
    table.add_column("Benchmark Suite", style="bold cyan")
    table.add_column("Tasks", justify="right", style="green")
    table.add_column("Domain Category", style="yellow")

    categories = {
        "humaneval_plus": "Algorithmic Code Synthesis & Edge-Case Validation",
        "mbpp_plus": "Mostly Basic Python Real-World Utility Problems",
        "math_reasoning": "DeepSeek-R1 Style Multi-Step Mathematical & Algorithmic Reasoning",
        "swe_repo": "Repository-Level Bug Fixing & Deep Config Merging",
        "tool_use": "Agentic Tool Calling & JSON-RPC MCP Function Calling",
    }

    for name, count in catalogs.items():
        table.add_row(name, str(count), categories.get(name, "General"))

    console.print(table)


@harness_group.command(name='run')
@click.option('--benchmark', '-b', default='all', help='Benchmark suite to evaluate (humaneval_plus, mbpp_plus, math_reasoning, swe_repo, tool_use, all)')
@click.option('--model', '-m', default='auto', help='Model to evaluate')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of tasks evaluated')
@click.option('--workers', '-w', default=4, type=int, help='Parallel evaluation workers')
@click.option('--output-file', '-o', default=None, help='File path to export Markdown evaluation report')
@click.option('--dry-run', is_flag=True, help='Simulate harness evaluation without LLM calls')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def harness_run_cmd(benchmark, model, limit, workers, output_file, dry_run, as_json):
    """Run comprehensive multi-domain model evaluation and compute Pass@k metrics."""
    from saleha.harness import harness, reporter

    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Executing Saleha Harness on '{model}' (Suite: {benchmark})..."),
        console=console,
    ) as progress:
        progress.add_task("harness", total=None)
        report = harness.evaluate(
            model=model,
            benchmark=benchmark,
            limit=limit,
            workers=workers,
            dry_run=dry_run
        )

    if as_json:
        payload = {
            "model": report.model_name,
            "timestamp": report.timestamp,
            "total_tasks": report.total_tasks,
            "overall_pass_at_1": report.overall_pass_at_1,
            "overall_pass_at_5": report.overall_pass_at_5,
            "avg_latency_sec": report.avg_latency_sec,
            "avg_tokens_per_sec": report.avg_tokens_per_sec,
            "benchmarks": {
                k: {
                    "total": v.total_tasks,
                    "passed": v.passed_tasks,
                    "pass_at_1": v.pass_at_1,
                    "avg_latency": v.avg_latency_sec
                } for k, v in report.benchmark_summaries.items()
            }
        }
        click.echo(json.dumps(payload, ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title=f"🧪 Saleha Harness Evaluation — Model: {report.model_name}", border_style="green")
    table.add_column("Benchmark Suite", style="bold cyan")
    table.add_column("Tasks", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Pass@1", justify="right", style="bold green")
    table.add_column("Avg Latency", justify="right", style="yellow")

    for name, summ in report.benchmark_summaries.items():
        table.add_row(name, str(summ.total_tasks), str(summ.passed_tasks), f"{summ.pass_at_1}%", f"{summ.avg_latency_sec}s")

    console.print(table)
    console.print(Panel(
        f"[bold cyan]Model:[/] {report.model_name}\n"
        f"[bold cyan]Overall Pass@1:[/] [bold green]{report.overall_pass_at_1}%[/]\n"
        f"[bold cyan]Unbiased Pass@5 Estimate:[/] [bold green]{report.overall_pass_at_5}%[/]\n"
        f"[bold cyan]Average Latency:[/] {report.avg_latency_sec}s / task\n"
        f"[bold cyan]Throughput:[/] {report.avg_tokens_per_sec} tok/sec",
        title="[bold green]🏆 Harness Evaluation Summary[/]",
        border_style="green"
    ))

    if output_file:
        reporter.export_markdown(report, output_file)
        console.print(f"[bold green]💾 Markdown report exported to:[/] {output_file}")


@harness_group.command(name='leaderboard')
def harness_leaderboard_cmd():
    """Display persistent model ranking leaderboard."""
    from saleha.harness import reporter
    reporter.render_leaderboard()


# ==============================================================================
# NEXT-GEN AI SUPERPOWERS (VISION, FUZZ, RAG, AUTODOC, DB, WORKSPACE)
# ==============================================================================

@cli.command(name='vision')
@click.argument('spec')
@click.option('--framework', '-f', default='react', type=click.Choice(['react', 'html', 'flutter']), help='Target UI framework')
@click.option('--name', '-n', default='GeneratedComponent', help='Component name')
@click.option('--image', '-i', default=None, type=click.Path(exists=True),
              help='Screenshot/wireframe image -- REAL vision model se analyze hota hai (llava/qwen-vl)')
@click.option('--output-file', '-o', default=None, help='Save generated code to file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def vision_cmd(spec, framework, name, image, output_file, as_json):
    """Synthesize UI code from specs OR from a real screenshot via local vision models.

    Example: saleha vision "responsive dashboard" --image ./mockup.png -f react
    """
    from saleha.core.vision_coder import vision_coder
    res = vision_coder.synthesize_ui(layout_spec=spec, framework=framework,
                                     component_name=name, image_source=image)

    if as_json:
        click.echo(json.dumps({
            "framework": res.framework,
            "component_name": res.component_name,
            "dependencies": res.dependencies,
            "code": res.code,
            "used_vision": res.used_vision,
            "model_used": res.model_used,
            "source": res.source_note,
        }, ensure_ascii=True))
        return

    source_label = f"[green]👁️ {res.source_note}[/]" if res.used_vision else f"[dim]{res.source_note}[/]"
    console.print(Panel(
        f"[bold cyan]Framework:[/] {res.framework.upper()}\n"
        f"[bold cyan]Component:[/] {res.component_name}\n"
        f"[bold cyan]Dependencies:[/] {', '.join(res.dependencies)}\n"
        f"[bold cyan]Source:[/] {source_label}",
        title="[bold green]🖼️ Saleha Vision UI Synthesizer[/]",
        border_style="green"
    ))

    syntax = Syntax(res.code, "typescript" if framework == "react" else ("dart" if framework == "flutter" else "html"), theme="monokai", line_numbers=True)
    console.print(syntax)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(res.code)
        console.print(f"\n[bold green]💾 Saved component to:[/] {output_file}")


@cli.command(name='fuzz')
@click.argument('func_name', default='process')
@click.option('--mutations', '-m', default=5, type=int, help='Number of mutation payloads to test')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def fuzz_cmd(func_name, mutations, as_json):
    """Execute automated security mutation fuzzing against code functions."""
    from saleha.core.api_fuzzer import api_fuzzer
    mock_code = f"def {func_name}(val):\n    if len(str(val)) > 100:\n        raise ValueError('Buffer overflow attempt')\n    return {{'status': 'ok'}}"
    report = api_fuzzer.fuzz_function(code=mock_code, func_name=func_name, mutations=mutations)

    if as_json:
        click.echo(json.dumps({
            "target": report.target,
            "total_mutations": report.total_mutations,
            "vulnerabilities_found": report.vulnerabilities_found,
            "crashes_found": report.crashes_found,
            "findings": [f.__dict__ for f in report.findings]
        }, ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title=f"🦹 Saleha API Security Fuzzer — Target: {report.target}()", border_style="red")
    table.add_column("Category", style="bold cyan")
    table.add_column("Payload Preview", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Result", style="yellow")

    for f in report.findings:
        status_txt = "[red]💥 CRASH[/]" if f.status == "CRASH" else "[green]🛡️ SAFE[/]"
        table.add_row(f.category, f.payload[:30], status_txt, f.details[:50])

    console.print(table)
    console.print(Panel(
        f"[bold cyan]Total Mutations:[/] {report.total_mutations}\n"
        f"[bold cyan]Crashes / Exceptions:[/] [{'red' if report.crashes_found else 'green'}]{report.crashes_found}[/]",
        title="[bold green]Fuzzing Summary[/]",
        border_style="green"
    ))


@cli.command(name='rag')
@click.argument('question')
@click.option('--path', '-p', default='.', help='Codebase path to index')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def rag_cmd(question, path, as_json):
    """Natural language architectural Q&A fused with AST Dependency Graph."""
    from saleha.core.graph_rag import graph_rag
    ans = graph_rag.query(question=question, root_dir=path)

    if as_json:
        click.echo(json.dumps({
            "question": ans.question,
            "answer": ans.answer,
            "relevant_files": ans.relevant_files,
            "key_symbols": ans.key_symbols,
            "call_hierarchy": ans.call_hierarchy
        }, ensure_ascii=True))
        return

    console.print(Panel(
        f"[bold cyan]Question:[/] {ans.question}\n"
        f"[bold cyan]Relevant Files:[/] {', '.join(ans.relevant_files[:5]) or 'All'}\n"
        f"[bold cyan]Key Symbols:[/] {', '.join(ans.key_symbols[:5]) or 'General'}",
        title="[bold green]🧠 Saleha Graph RAG Codebase Q&A[/]",
        border_style="green"
    ))
    console.print(Markdown(ans.answer))


@cli.command(name='autodoc')
@click.argument('path', default='.')
@click.option('--output-dir', '-o', default=None, help='Directory to export Markdown docs')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def autodoc_cmd(path, output_dir, as_json):
    """Generate Markdown API docs and Mermaid architecture diagrams from AST."""
    from saleha.core.autodoc_generator import autodoc_generator
    res = autodoc_generator.generate_docs_for_directory(root_dir=path)

    if as_json:
        click.echo(json.dumps({
            "total_modules": res.total_modules,
            "total_classes": res.total_classes,
            "total_functions": res.total_functions,
            "mermaid_diagram": res.mermaid_diagram,
            "markdown_docs_preview": res.markdown_docs[:300]
        }, ensure_ascii=True))
        return

    console.print(Panel(
        f"[bold cyan]Modules Scanned:[/] {res.total_modules}\n"
        f"[bold cyan]Classes Documented:[/] {res.total_classes}\n"
        f"[bold cyan]Functions Documented:[/] {res.total_functions}",
        title="[bold green]📚 Saleha Auto-Documentation Generator[/]",
        border_style="green"
    ))

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        doc_path = os.path.join(output_dir, "API_REFERENCE.md")
        diag_path = os.path.join(output_dir, "ARCHITECTURE_DIAGRAM.mermaid")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(res.markdown_docs)
        with open(diag_path, "w", encoding="utf-8") as f:
            f.write(res.mermaid_diagram)
        console.print(f"[bold green]💾 Exported docs to:[/] {output_dir}")


@cli.group(name='db')
def db_group():
    """Database schema analysis, index optimization, and migrations."""
    pass


@db_group.command(name='optimize')
@click.argument('schema_or_file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def db_optimize_cmd(schema_or_file, as_json):
    """Analyze SQL DDL or models for missing indexes and generate UP/DOWN migrations."""
    from saleha.core.db_optimizer import db_optimizer
    content = schema_or_file
    if os.path.isfile(schema_or_file):
        with open(schema_or_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

    analysis = db_optimizer.analyze_schema(content)

    if as_json:
        click.echo(json.dumps({
            "tables_found": analysis.tables_found,
            "missing_indexes": analysis.missing_indexes,
            "n_plus_one_risks": analysis.n_plus_one_risks,
            "migration_sql_up": analysis.migration_sql_up,
            "migration_sql_down": analysis.migration_sql_down
        }, ensure_ascii=True))
        return

    console.print(Panel(
        f"[bold cyan]Tables Found:[/] {', '.join(analysis.tables_found) or 'None'}\n"
        f"[bold cyan]Missing Indexes Detected:[/] {len(analysis.missing_indexes)}\n"
        f"[bold cyan]N+1 Query Risks:[/] {len(analysis.n_plus_one_risks)}",
        title="[bold green]🗄️ Database Schema & Index Optimizer[/]",
        border_style="green"
    ))
    console.print("\n[bold green]⚡ Generated Migration (UP):[/]")
    console.print(Syntax(analysis.migration_sql_up, "sql", theme="monokai"))


@cli.group(name='workspace')
def workspace_group():
    """Multi-Repo & Monorepo synchronized workspace coordination."""
    pass


@workspace_group.command(name='status')
@click.option('--path', '-p', default='.', help='Workspace root path')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def workspace_status_cmd(path, as_json):
    """Audit branch status and uncommitted changes across all workspace repos."""
    from saleha.core.workspace_coordinator import workspace_coordinator
    statuses = workspace_coordinator.get_workspace_status(root_dir=path)

    if as_json:
        click.echo(json.dumps([s.__dict__ for s in statuses], ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title="🌐 Multi-Repo Workspace Status", border_style="cyan")
    table.add_column("Repository", style="bold cyan")
    table.add_column("Current Branch", style="yellow")
    table.add_column("Clean Status", justify="center")
    table.add_column("Uncommitted Files", justify="right")

    for s in statuses:
        clean_txt = "[green]✅ CLEAN[/]" if s.is_clean else "[yellow]⚠️ DIRTY[/]"
        table.add_row(s.name, s.current_branch, clean_txt, str(s.uncommitted_count))

    console.print(table)


# ==============================================================================
# ULTIMATE ENTERPRISE HORIZONS (DEPLOY, LOADTEST, SRE, SIDECAR)
# ==============================================================================

@cli.command(name='deploy')
@click.option('--target', '-t', default='all', type=click.Choice(['docker', 'k8s', 'all']), help='Deployment manifest target')
@click.option('--output-dir', '-o', default='./deploy', help='Output directory for manifests')
@click.option('--name', '-n', default='saleha-service', help='Service name')
@click.option('--port', '-p', default=8000, type=int, help='Exposed port')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def deploy_cmd(target, output_dir, name, port, as_json):
    """Generate production-ready Dockerfile, Compose, and Kubernetes manifests."""
    from saleha.core.deployer import cloud_deployer
    pkg = cloud_deployer.generate_package(root_dir=".", app_name=name, port=port)
    written = cloud_deployer.export_package(pkg, output_dir=output_dir)

    if as_json:
        click.echo(json.dumps({
            "app_name": pkg.app_name,
            "runtime": pkg.runtime,
            "port": pkg.port,
            "output_dir": output_dir,
            "files_generated": [os.path.basename(f) for f in written]
        }, ensure_ascii=True))
        return

    console.print(Panel(
        f"[bold cyan]App Name:[/] {pkg.app_name}\n"
        f"[bold cyan]Detected Runtime:[/] {pkg.runtime.upper()}\n"
        f"[bold cyan]Exposed Port:[/] {pkg.port}\n"
        f"[bold cyan]Output Directory:[/] {output_dir}\n"
        f"[bold green]Files Generated:[/]\n" + "\n".join([f"  • {os.path.basename(f)}" for f in written]),
        title="[bold green]☁️ Saleha 1-Click Cloud & K8s Deployer[/]",
        border_style="green"
    ))


@cli.command(name='loadtest')
@click.argument('url', default='http://localhost:8000/api/status')
@click.option('--concurrency', '-c', default=10, type=int, help='Concurrent users / threads')
@click.option('--requests', '-r', default=50, type=int, help='Total requests to send')
@click.option('--dry-run', is_flag=True, help='Simulate load benchmark')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def loadtest_cmd(url, concurrency, requests, dry_run, as_json):
    """Execute high-concurrency API load testing and percentile benchmarks."""
    from saleha.core.load_tester import load_tester

    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Executing load test against '{url}' ({requests} requests, {concurrency} workers)..."),
        console=console,
    ) as progress:
        progress.add_task("loadtest", total=None)
        res = load_tester.run_load_test(url=url, concurrency=concurrency, total_requests=requests, dry_run=dry_run)

    if as_json:
        click.echo(json.dumps(res.__dict__, ensure_ascii=True))
        return

    from rich.table import Table
    table = Table(title=f"⚡ Load Test Benchmark — {res.url}", border_style="cyan")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", justify="right", style="bold green")

    table.add_row("Total Requests", str(res.total_requests))
    table.add_row("Successful", str(res.successful_requests))
    table.add_row("Failed", str(res.failed_requests))
    table.add_row("Throughput", f"{res.requests_per_sec} req/sec")
    table.add_row("Avg Latency", f"{res.avg_latency_ms} ms")
    table.add_row("p50 (Median)", f"{res.p50_ms} ms")
    table.add_row("p95", f"{res.p95_ms} ms")
    table.add_row("p99", f"{res.p99_ms} ms")

    console.print(table)


@cli.group(name='sre')
def sre_group():
    """Autonomous SRE Incident Responder and Log Analyzer."""
    pass


@sre_group.command(name='analyze')
@click.argument('log_or_file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def sre_analyze_cmd(log_or_file, as_json):
    """Analyze production stacktrace and synthesize emergency hotfix patch."""
    from saleha.core.sre_responder import sre_responder
    content = log_or_file
    if os.path.isfile(log_or_file):
        with open(log_or_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

    report = sre_responder.analyze_log(content)

    if as_json:
        click.echo(json.dumps(report.__dict__, ensure_ascii=True))
        return

    sev_color = "red" if report.severity in ("CRITICAL", "HIGH") else "yellow"
    console.print(Panel(
        f"[bold cyan]Exception:[/] [{sev_color}]{report.error_type}[/]\n"
        f"[bold cyan]Severity:[/] [{sev_color}]{report.severity}[/]\n"
        f"[bold cyan]Offending Location:[/] {report.offending_file or 'N/A'}:{report.offending_line or 'N/A'}\n"
        f"[bold cyan]Message:[/] {report.error_message}\n\n"
        f"[bold yellow]Root Cause Analysis (RCA):[/]\n{report.root_cause_analysis}",
        title=f"[{sev_color}]🚨 Autonomous SRE Incident Report[/]",
        border_style=sev_color
    ))
    console.print("\n[bold green]🩹 Emergency Hotfix Patch:[/]")
    console.print(Syntax(report.hotfix_patch, "python", theme="monokai"))


@cli.command(name='sidecar')
@click.option('--host', default='127.0.0.1', help='Host address')
@click.option('--port', default=7890, type=int, help='Port to serve')
@click.option('--open/--no-open', 'open_browser', default=True, help='Open in browser')
def sidecar_cmd(host, port, open_browser):
    """Launch the floating desktop AI companion daemon on localhost:7890."""
    console.print(Panel(
        f"[bold cyan]URL:[/] http://{host}:{port}\n"
        f"[bold cyan]Service:[/] Floating Desktop Sidecar Companion\n"
        f"[dim]Press Ctrl+C in terminal to stop daemon[/]",
        title="[bold green]🪟 Saleha Desktop Sidecar Active[/]",
        border_style="green"
    ))
    from saleha.core.sidecar_daemon import sidecar_daemon
    sidecar_daemon.run(host=host, port=port, open_browser=open_browser)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    cli()