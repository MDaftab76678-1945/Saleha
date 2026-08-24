"""
Saleha Core: Dual MCP (Model Context Protocol) Engine

Provides a standard MCP Server (JSON-RPC 2.0 over stdio/HTTP) exposing Saleha's
swarm delivery, DAG task execution, AST security scanning, sandboxing, and vector memory,
as well as an MCP Client to consume tools from external MCP servers.
"""

import sys
import json
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

from saleha import __version__
from saleha.core.team_orchestrator import TeamOrchestrator
from saleha.core.dag_engine import TaskDAG
from saleha.core.security_scanner import ASTSecurityScanner
from saleha.core.sandbox_runner import SandboxRunner
from saleha.core.memory_store import memory_store


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    inputSchema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]


class MCPServer:
    """Standard Model Context Protocol Server (JSON-RPC 2.0)."""

    def __init__(self, server_name: str = "saleha-ai-server"):
        self.server_name = server_name
        self.server_version = __version__
        self.tools: Dict[str, MCPToolDefinition] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        # 1. Team Swarm Delivery
        self.register_tool(
            name="saleha_team_swarm",
            description="Run full 5-stage autonomous multi-agent swarm delivery (PM -> Architect -> SDE -> Security -> QA).",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "High-level software goal or feature request"},
                    "debate": {"type": "boolean", "description": "Enable multi-agent deliberation debate"}
                },
                "required": ["goal"]
            },
            handler=self._handle_team_swarm
        )

        # 2. Parallel DAG Execution
        self.register_tool(
            name="saleha_dag_execute",
            description="Execute complex engineering goals using a parallel Directed Acyclic Graph (DAG) of agents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Goal to decompose and execute in DAG"}
                },
                "required": ["goal"]
            },
            handler=self._handle_dag_execute
        )

        # 3. Deep AST Security SAST Scanner
        self.register_tool(
            name="saleha_sast_scan",
            description="Scan codebase or file for SQL injection, hardcoded secrets, unsafe execution, and weak crypto.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to audit (default '.')", "default": "."},
                    "severity": {"type": "string", "enum": ["high", "medium", "low", "all"], "default": "all"}
                }
            },
            handler=self._handle_sast_scan
        )

        # 4. Isolated VirtualEnv Sandbox Execution
        self.register_tool(
            name="saleha_sandbox_run",
            description="Safely execute Python code inside an isolated ephemeral sandbox environment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python source code to execute"},
                    "dependencies": {"type": "array", "items": {"type": "string"}, "description": "List of packages to install"}
                },
                "required": ["code"]
            },
            handler=self._handle_sandbox_run
        )

        # 5. Semantic Vector Memory Recall
        self.register_tool(
            name="saleha_memory_recall",
            description="Search verified architecture patterns and solutions in long-term memory via vector semantics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Conceptual search query"}
                },
                "required": ["query"]
            },
            handler=self._handle_memory_recall
        )

    def register_tool(self, name: str, description: str, inputSchema: Dict[str, Any], handler: Callable):
        self.tools[name] = MCPToolDefinition(name=name, description=description, inputSchema=inputSchema, handler=handler)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema
            }
            for t in self.tools.values()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self.tools:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool '{name}' not found."}]}
        try:
            res = self.tools[name].handler(arguments)
            return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}]}
        except (TypeError, ValueError, KeyError) as e:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool execution failed: {str(e)}"}]}

    def handle_json_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handles incoming JSON-RPC 2.0 MCP request."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": self.server_name, "version": self.server_version},
                    "capabilities": {"tools": {}}
                }
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.list_tools()}
            }

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = self.call_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found."}
        }

    # Tool Handlers
    def _handle_team_swarm(self, args: Dict[str, Any]) -> Dict[str, Any]:
        goal = args.get("goal", "")
        debate = args.get("debate", False)
        res = TeamOrchestrator().run_team_workflow(goal=goal, debate=debate)
        return {
            "success": res.success,
            "goal": res.goal,
            "stages_completed": res.stages_completed,
            "solution_code": res.code,
            "test_code": res.test_code,
            "security_report": res.security_report
        }

    def _handle_dag_execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        goal = args.get("goal", "")
        dag = TaskDAG.build_default_dag_for_goal(goal=goal)
        res = dag.execute_parallel(max_workers=4)
        return {
            "success": res.success,
            "goal": res.goal,
            "total_tasks": res.total_tasks,
            "completed_tasks": res.completed_tasks,
            "total_time": res.total_time,
            "mermaid_graph": res.mermaid_graph
        }

    def _handle_sast_scan(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path", ".")
        scanner = ASTSecurityScanner()
        report = scanner.scan_directory(path)
        return {
            "total_files": report.total_files_scanned,
            "total_vulnerabilities": report.total_vulnerabilities,
            "high": report.high_count,
            "medium": report.medium_count,
            "low": report.low_count,
            "vulnerabilities": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "file": v.file_path,
                    "line": v.line_number,
                    "description": v.description,
                    "remediation": v.remediation
                }
                for v in report.vulnerabilities
            ]
        }

    def _handle_sandbox_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        code = args.get("code", "")
        deps = args.get("dependencies", [])
        runner = SandboxRunner()
        res = runner.run_in_sandbox(code, dependencies=deps)
        return {
            "success": res.success,
            "output": res.output,
            "error": res.error,
            "exit_code": res.exit_code,
            "execution_time": res.execution_time
        }

    def _handle_memory_recall(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        results = memory_store.semantic_search(query, top_k=3)
        return {
            "query": query,
            "results": [
                {
                    "id": entry.id,
                    "goal": entry.goal,
                    "score": score,
                    "code_preview": entry.code[:150],
                    "tags": entry.tags
                }
                for entry, score in results
            ]
        }

    def run_stdio_loop(self):
        """Runs the standard MCP JSON-RPC loop over standard input/output."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_json_rpc(req)
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except (json.JSONDecodeError, OSError, KeyError) as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()


class MCPClient:
    """Client for invoking external MCP servers via JSON-RPC over stdio."""

    def __init__(self, command: List[str]):
        self.command = command

    def execute_rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        try:
            proc = subprocess.run(
                self.command,
                input=json.dumps(req) + "\n",
                capture_output=True,
                text=True,
                timeout=15
            )
            if proc.returncode == 0 and proc.stdout:
                return json.loads(proc.stdout.strip())
        except Exception:
            return None
        return None

