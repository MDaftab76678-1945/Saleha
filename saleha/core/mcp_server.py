"""SalehaMCPServer: Universal JSON-RPC 2.0 Model Context Protocol (MCP) Server for IDE Integrations."""

from __future__ import annotations
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from saleha.core.neuro_symbolic_engine import neuro_symbolic_engine
from saleha.core.ephemeral_container_runner import container_runner
from saleha.core.notebook_engine import notebook_engine


@dataclass
class MCPToolDefinition:
    """Represents an MCP Tool specification."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class SalehaMCPServer:
    """Standard Model Context Protocol (MCP) server exposing Saleha's autonomous agents,

    AST compiler, Ephemeral Sandbox, and Notebook Engine to Cursor, VS Code, and Claude Desktop.
    """

    def __init__(self):
        self.server_name = "saleha-mcp-server"
        self.version = "3.2.0"
        self._tools: Dict[str, MCPToolDefinition] = {
            "execute_swarm_dag": MCPToolDefinition(
                name="execute_swarm_dag",
                description="Executes a full 27-agent autonomous DAG pipeline for any software goal.",
                inputSchema={
                    "type": "object",
                    "properties": {"goal": {"type": "string", "description": "The engineering task or architecture goal"}},
                    "required": ["goal"],
                },
            ),
            "validate_ast_code": MCPToolDefinition(
                name="validate_ast_code",
                description="Validates Python code for deterministic AST syntax, PEP typing, and OWASP security.",
                inputSchema={
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Python source code"}},
                    "required": ["code"],
                },
            ),
            "run_container_sandbox": MCPToolDefinition(
                name="run_container_sandbox",
                description="Executes arbitrary code in an isolated Ephemeral Container Sandbox (256MB RAM / 1.0 CPU).",
                inputSchema={
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Code to execute in sandbox"}},
                    "required": ["code"],
                },
            ),
            "score_code_rlif": MCPToolDefinition(
                name="score_code_rlif",
                description="Computes Neuro-Symbolic Invariant RLIF Fitness Score (0.0 - 1.0) with detailed diagnostics.",
                inputSchema={
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Python source code to score"}},
                    "required": ["code"],
                },
            ),
            "synthesize_notebook": MCPToolDefinition(
                name="synthesize_notebook",
                description="Generates an interactive Jupyter .ipynb computational notebook with AST invariants.",
                inputSchema={
                    "type": "object",
                    "properties": {"topic": {"type": "string", "description": "Topic or ML pipeline domain"}},
                    "required": ["topic"],
                },
            ),
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns the list of available MCP tools in standard format."""
        return [asdict(t) for t in self._tools.values()]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool call and returns standard MCP JSON response."""
        if tool_name not in self._tools:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool '{tool_name}' not found."}]}

        if tool_name == "validate_ast_code" or tool_name == "score_code_rlif":
            code = arguments.get("code", "")
            score = neuro_symbolic_engine.score_code(code)
            return {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": f"AST Valid: {score.ast_valid} | Composite Score: {score.composite_score * 100:.1f}%\n"
                                + "\n".join(f"- {n}" for n in score.feedback_notes),
                    }
                ],
            }

        if tool_name == "run_container_sandbox":
            code = arguments.get("code", "")
            res = container_runner.run_code(code)
            return {
                "isError": not res.success,
                "content": [
                    {
                        "type": "text",
                        "text": f"Sandbox ExitCode: {res.exit_code} ({res.duration_ms}ms)\nOutput:\n{res.output}\nError:\n{res.error}",
                    }
                ],
            }

        if tool_name == "synthesize_notebook":
            topic = arguments.get("topic", "Data Science Pipeline")
            doc = notebook_engine.create_notebook(topic)
            ipynb_json = notebook_engine.export_to_ipynb(doc)
            return {
                "isError": False,
                "content": [{"type": "text", "text": f"Synthesized {len(doc.cells)} cells.\nJupyter JSON:\n{ipynb_json[:400]}..."}],
            }

        if tool_name == "execute_swarm_dag":
            # The real orchestrator (saleha/orchestrator.py::SalehaOrchestrator.execute_task)
            # is a heavyweight, potentially long-running, model-calling entry
            # point with no timeout/cancellation contract suitable for a
            # synchronous MCP tool call. Rather than either block an IDE's
            # request for an unbounded time or fabricate a "100% Invariants
            # Verified" result with zero agents actually run (the previous
            # behavior of this branch), this tool honestly reports that it
            # is not wired up yet instead of inventing a result.
            goal = arguments.get("goal", "Generic Task")
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"execute_swarm_dag is not implemented as a synchronous MCP "
                            f"tool call -- the real orchestrator "
                            f"(SalehaOrchestrator.execute_task) is a long-running, "
                            f"model-calling pipeline with no bounded-time contract. "
                            f"Run 'saleha build \"{goal}\"' from the CLI instead."
                        ),
                    }
                ],
            }

        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Tool '{tool_name}' has no implementation."}],
        }

    def handle_jsonrpc_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Handles a standard JSON-RPC 2.0 protocol request."""
        req_id = req.get("id", 1)
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.list_tools()}}

        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            result = self.call_tool(name, args)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not supported."},
        }


saleha_mcp_server = SalehaMCPServer()
