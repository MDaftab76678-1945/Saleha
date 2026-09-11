"""
Saleha CLI - Advanced Command Line Interface
उद्देश्य: Terminal से Saleha की पूरी ताकत इस्तेमाल करना

Naya kya hai: `saleha stats` aur `saleha history` commands add hue hain,
taaki persistent data dekhne ke liye lambi `python -c "..."` command na
likhni pade.
"""

from __future__ import annotations

import click
import sys
import os
import subprocess
from pathlib import Path

import re
import time
import json
import io
import contextlib
from contextlib import redirect_stdout
from typing import Optional, Tuple, List, Dict, Any, Callable, Union, Set, TYPE_CHECKING
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

from saleha.cli.dashboard import render_dashboard

if TYPE_CHECKING:
    from saleha.core.smart_router import SmartRouter
    from saleha.agents.base_agent import BaseAgent
    from saleha.agents.planner import PlannerAgent
    from saleha.agents.coder import CoderAgent
    from saleha.agents.tester import TesterAgent
    from saleha.agents.debugger import DebuggerAgent
    from saleha.orchestrator import SalehaOrchestrator
    from saleha.core.project_builder import ProjectBuilder
    from saleha.core.team_orchestrator import TeamOrchestrator
    from saleha.core.skill_registry import registry as skill_registry, load_builtin_skills
    from saleha.core.agent_profile_loader import profile_registry
    from saleha.core.memory_store import memory_store
    from saleha.core.codebase_indexer import CodebaseIndexer, SmartPatcher
    from saleha.core.deliberation_engine import DeliberationEngine
    from saleha.core.tool_calling import global_tool_registry
    from saleha.core.sandbox_runner import SandboxRunner
    from saleha.core.docker_sandbox import DockerSandboxRunner
    from saleha.core.polyglot_indexer import PolyglotIndexer
    from saleha.core.pr_generator import PRGenerator
    from saleha.core.security_scanner import ASTSecurityScanner
    from saleha.core.dag_engine import TaskDAG, TaskNode
    from saleha.core.mcp_engine import MCPServer
    from saleha.ci.bot import PRReviewBot
    from saleha.core.hybrid_gateway import gateway as hybrid_gateway
    from saleha.server.web_server import run_web_studio
    from saleha.cli.repl import start_repl
    from saleha.cli.tui_canvas import start_tui_canvas
    from saleha.cli.dashboard import run_live_dashboard
    from saleha.core.agentic_loop import AgentLoop
    from saleha.core.repo_watcher import repo_watcher
    from saleha.core.swe_bench_harness import swe_bench
    from saleha.core.lsp_engine import lsp_engine
    from saleha.core.cloud_deployer import cloud_deployer
    from saleha.core.db_optimizer import db_optimizer

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
    "repo_watcher": ("saleha.core.repo_watcher", "repo_watcher"),
    "swe_bench": ("saleha.core.swe_bench_harness", "swe_bench"),
    "lsp_engine": ("saleha.core.lsp_engine", "lsp_engine"),
    "cloud_deployer": ("saleha.core.cloud_deployer", "cloud_deployer"),
    "db_optimizer": ("saleha.core.db_optimizer", "db_optimizer"),
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


# ==============================================================================
# AGENT COMMAND - Autonomous ReAct Loop with Surgical AST Tools
# ==============================================================================


# ==============================================================================
# PLAN COMMAND - Generate Plan Only
# ==============================================================================


# ==============================================================================
# CODE COMMAND - Generate Code Only
# ==============================================================================


# ============================================================================
# ASK COMMAND - One-shot assistant response
# ============================================================================


# ==============================================================================
# TEST COMMAND - Test Code
# ==============================================================================


# ============================================================================
# DEBUG COMMAND - Diagnose and repair code
# ============================================================================


# ==============================================================================
# MODELS COMMAND - Show Available Models
# ==============================================================================


# ============================================================================
# SKILLS COMMAND - Show registered local skills
# ============================================================================


# ============================================================================
# AGENTS COMMAND - Show loaded dynamic agent profiles
# ============================================================================


# ==============================================================================
# PROJECT COMMAND - Multi-file Project Builder (Naya)
# ==============================================================================


# ==============================================================================
# TEAM / SWARM COMMAND - Multi-Agent Collaborative Delivery Pipeline
# ==============================================================================


# ==============================================================================
# SCAN & REFACTOR COMMANDS - Codebase AST Intelligence & Smart Patching
# ==============================================================================


# ==============================================================================
# TOOLS & SANDBOX COMMANDS - Dynamic Tool Calling & VirtualEnv Sandbox Runner
# ==============================================================================


# ==============================================================================
# SERVE & PR COMMANDS - Web Studio Server & Autonomous Git PR Agent
# ==============================================================================


# ==============================================================================
# DOCTOR COMMAND - Diagnostic checklist (Naya -- is session ke real bugs se banaya)
# ==============================================================================


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


# ============================================================================
# HISTORY COMMAND - Show recent task history (Naya)
# ============================================================================


# ==============================================================================
# AUDIT COMMAND - Show execution audit records
# ==============================================================================


# ==============================================================================
# SAST COMMAND - Deep AST Security Vulnerability Scanner
# ==============================================================================


# ==============================================================================
# DAG COMMAND - Parallel Directed Acyclic Graph Engine
# ==============================================================================


# ==============================================================================
# CHAT & REPL COMMANDS - Interactive Pair-Programming Shell
# ==============================================================================


# ==============================================================================
# AGENT COMMAND - Autonomous ReAct Tool-Use Loop (v1.1 keystone)
# ==============================================================================


def _one_line(text: str) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:100] + ("..." if len(text) > 100 else "")


# ==============================================================================
# EDIT COMMAND - Multi-File Surgical Editor (C1)
# ==============================================================================


# ==============================================================================
# PROFILE COMMAND - Hardware Telemetry Profiler (v1.6)
# ==============================================================================


# ==============================================================================
# METRICS COMMAND - Structured Run Observability (B3)
# ==============================================================================


# ==============================================================================
# DASHBOARD / UI COMMAND - Live Operational Terminal Dashboard
# ==============================================================================


# ==============================================================================
# MEMORY COMMAND GROUP - Long-Term Knowledge Base & Solution Cache
# ==============================================================================


# STATUS COMMAND - Show System Status
# ==============================================================================


# ==============================================================================
# INTERACTIVE COMMAND - Interactive Shell
# ==============================================================================


# ==============================================================================
# MCP, CI/CD REVIEW, & TUI CANVAS COMMANDS
# ==============================================================================


# ==============================================================================
# ENCRYPTED SECRET VAULT COMMANDS
# ==============================================================================


# ==============================================================================
# BENCHMARK EVALUATOR COMMAND
# ==============================================================================


# ==============================================================================
# 6-HORIZON DEEP CAPABILITY COMMANDS
# ==============================================================================


# ==============================================================================
# APEX FRONTIER COMMANDS (REPL, PR REVIEW, VOICE, SWE-BENCH)
# ==============================================================================


# ==============================================================================
# SALEHA HARNESS COMMANDS (DEEPSEEK-STYLE EVALUATION HARNESS)
# ==============================================================================


# ==============================================================================
# NEXT-GEN AI SUPERPOWERS (VISION, FUZZ, RAG, AUTODOC, DB, WORKSPACE)
# ==============================================================================


# ==============================================================================
# ULTIMATE ENTERPRISE HORIZONS (DEPLOY, LOADTEST, SRE, SIDECAR)
# ==============================================================================


# ==============================================================================
# SALEHA V2.0 MAJOR SYSTEMS
# ==============================================================================


# ==============================================================================
# DOOM ENGINE & SALEHA SWARM CLI COMMANDS
# ==============================================================================


# ==============================================================================
# SALEHA v2.6: AGENTSKILLS 1,000+ CATALOG & UNIVERSAL MCP HUB COMMANDS
# ==============================================================================


# ==============================================================================
# SPECIALIZED ORCHESTRATOR CLI COMMANDS (v2.6.0)
# ==============================================================================


from saleha.cli.monorepo_cli import monorepo_group
from saleha.cli.demo_cli import dogfood_cmd
from saleha.cli.benchmark_cli import benchmark_cmd
from saleha.cli.info_cli import info_cmd
from saleha.cli.start_cli import start_cmd
from saleha.cli.release_cli import release_cmd
from saleha.cli.soul_cli import soul_group

# ==============================================================================
# Category modules: each import below runs that file's top-level
# @cli.command()/@cli.group() decorators, which is what actually registers
# those commands against the `cli` group defined above. Must run before the
# doom_group.add_command(...) calls just below, which need the real
# `doom_group` Click object -- imported explicitly from its own submodule
# (not via the generic `from saleha.cli.commands import doom_group` used for
# the others, which would bind this name to the submodule, not the group).
# ==============================================================================
from saleha.cli.commands import core_agentic  # noqa: F401
from saleha.cli.commands import deploy_infra  # noqa: F401
from saleha.cli.commands import desktop_web  # noqa: F401
from saleha.cli.commands import docs  # noqa: F401
from saleha.cli.commands.doom_group import doom_group
from saleha.cli.commands import git_group  # noqa: F401
from saleha.cli.commands import git_release  # noqa: F401
from saleha.cli.commands import harness_group  # noqa: F401
from saleha.cli.commands import hook_group  # noqa: F401
from saleha.cli.commands import hub_group  # noqa: F401
from saleha.cli.commands import indexing_graph  # noqa: F401
from saleha.cli.commands import mcp_group  # noqa: F401
from saleha.cli.commands import memory_context  # noqa: F401
from saleha.cli.commands import misc_tools  # noqa: F401
from saleha.cli.commands import quality_security  # noqa: F401
from saleha.cli.commands import research_experimental  # noqa: F401
from saleha.cli.commands import sandbox_exec  # noqa: F401
from saleha.cli.commands import scaffold  # noqa: F401
from saleha.cli.commands import scheduler  # noqa: F401
from saleha.cli.commands import self_improve  # noqa: F401
from saleha.cli.commands import skill_group  # noqa: F401
from saleha.cli.commands import swarm_team  # noqa: F401
from saleha.cli.commands import testing_bench  # noqa: F401
from saleha.cli.commands import tool_forge_cmd  # noqa: F401
from saleha.cli.commands import user  # noqa: F401
from saleha.cli.commands import vault_group  # noqa: F401
from saleha.cli.commands import voice_vision  # noqa: F401

cli.add_command(monorepo_group)
cli.add_command(dogfood_cmd)
cli.add_command(benchmark_cmd)
cli.add_command(info_cmd)
cli.add_command(start_cmd)
cli.add_command(release_cmd)
cli.add_command(soul_group)
doom_group.add_command(monorepo_group)
doom_group.add_command(dogfood_cmd)
doom_group.add_command(benchmark_cmd)
doom_group.add_command(info_cmd)
doom_group.add_command(start_cmd)
doom_group.add_command(release_cmd)
doom_group.add_command(soul_group)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    cli()
