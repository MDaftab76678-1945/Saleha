"""
Saleha Core: Dynamic Function & Tool Calling Framework

Provides dynamic tool registration, JSON schema generation, and execution
dispatching for Saleha autonomous agents.

Built-in Dynamic Tools:
1. `web_fetch`: HTTP client for retrieving external API schemas & documentation.
2. `file_search`: Workspace file and regex pattern search.
3. `sqlite_inspect`: SQLite schema and read-only query inspection.
4. `shell_exec`: Controlled command execution with AST/SafetyGuard protection.
"""

import os
import re
import ipaddress
import json
import socket
import sqlite3
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Any

from saleha.core.safety_guard import SafetyGuard


@dataclass
class ToolParameter:
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable[..., Any]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {
                "type": p.type,
                "description": p.description,
            }
            if p.default is not None:
                properties[p.name]["default"] = p.default
            if p.required:
                required.append(p.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }


@dataclass
class ToolCall:
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    output: str = ""
    error: str = ""


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._load_builtins()

    def register(self, tool_def: ToolDefinition):
        self._tools[tool_def.name] = tool_def

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_json_schema() for t in self._tools.values()]

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' is not registered."
            )
        if not tool.handler:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' has no handler defined."
            )
        try:
            res = tool.handler(**kwargs)
            return ToolResult(
                success=True,
                tool_name=tool_name,
                output=str(res)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Execution error in '{tool_name}': {str(e)}"
            )

    def _load_builtins(self):
        # 1. web_fetch tool
        _BLOCKED_HOST_SUFFIXES = (".internal", ".local", ".localhost", ".home.arpa")

        def _validate_http_url(url: str) -> str:
            """SSRF/file-read guard: sirf public http(s) URLs allowed.
            Pehle `file:///etc/passwd` aur internal hosts bhi fetch ho jaate the
            jab URL model-controlled tha."""
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"Blocked URL scheme '{parsed.scheme or 'none'}' -- only http/https allowed."
                )
            host = (parsed.hostname or "").lower()
            if not host:
                raise ValueError("URL has no hostname.")
            if host in ("localhost", "metadata.google.internal") or host.endswith(_BLOCKED_HOST_SUFFIXES):
                raise ValueError(f"Blocked internal host '{host}'.")
            try:
                addr_infos = socket.getaddrinfo(host, None)
            except OSError:
                raise ValueError(f"Cannot resolve host '{host}'.")
            for info in addr_infos:
                ip = ipaddress.ip_address(info[4][0])
                if (ip.is_private or ip.is_loopback or ip.is_link_local
                        or ip.is_reserved or ip.is_multicast):
                    raise ValueError(
                        f"Blocked non-public resolved address '{ip}' for host '{host}'."
                    )
            return url

        def _web_fetch(url: str, timeout: int = 10) -> str:
            _validate_http_url(url)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Saleha-Agent/0.1"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8", errors="replace")
                return content[:4000] + ("\n... [truncated]" if len(content) > 4000 else "")

        self.register(ToolDefinition(
            name="web_fetch",
            description="Fetches content from a URL via HTTP GET request.",
            parameters=[
                ToolParameter("url", "string", "Target URL to fetch content from.", required=True),
                ToolParameter("timeout", "integer", "HTTP timeout in seconds.", required=False, default=10),
            ],
            handler=_web_fetch
        ))

        # 2. file_search tool
        def _file_search(pattern: str, search_path: str = ".") -> str:
            matches = []
            regex = re.compile(pattern, re.IGNORECASE)
            for root, _, files in os.walk(search_path):
                for f in files:
                    if f.endswith((".py", ".md", ".json", ".yaml", ".txt", ".sql")):
                        full = os.path.join(root, f)
                        try:
                            with open(full, "r", encoding="utf-8", errors="ignore") as file_obj:
                                for line_no, line in enumerate(file_obj, 1):
                                    if regex.search(line):
                                        matches.append(f"{full}:{line_no}: {line.strip()}")
                                        if len(matches) >= 30:
                                            break
                        except (OSError, PermissionError):
                            continue
                if len(matches) >= 30:
                    break
            if not matches:
                return f"No matches found for pattern '{pattern}' in '{search_path}'."
            return "\n".join(matches)

        self.register(ToolDefinition(
            name="file_search",
            description="Searches files across the codebase for regex patterns or text.",
            parameters=[
                ToolParameter("pattern", "string", "Regex pattern to search for.", required=True),
                ToolParameter("search_path", "string", "Base directory path to search.", required=False, default="."),
            ],
            handler=_file_search
        ))

        # 3. sqlite_inspect tool
        def _sqlite_inspect(db_path: str, query: Optional[str] = None) -> str:
            if not os.path.isfile(db_path):
                return f"Database file not found: {db_path}"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            try:
                if not query:
                    # Return tables & schema
                    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
                    rows = cursor.fetchall()
                    if not rows:
                        return "Database has no tables."
                    return "\n\n".join([f"Table {r[0]}:\n{r[1]}" for r in rows])
                else:
                    # Enforce read-only queries
                    q_lower = query.strip().lower()
                    if not q_lower.startswith("select") and not q_lower.startswith("pragma") and not q_lower.startswith("explain"):
                        return "Error: Only read-only queries (SELECT, PRAGMA) are allowed in inspector."
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    return json.dumps(rows[:50], indent=2, ensure_ascii=False)
            finally:
                conn.close()

        self.register(ToolDefinition(
            name="sqlite_inspect",
            description="Inspects schema or executes read-only SELECT queries against a SQLite database.",
            parameters=[
                ToolParameter("db_path", "string", "Path to the SQLite database file.", required=True),
                ToolParameter("query", "string", "Optional read-only SQL query to execute.", required=False),
            ],
            handler=_sqlite_inspect
        ))

        # 4. shell_exec tool
        def _shell_exec(command: str, timeout: int = 15) -> str:
            from saleha.core.approval_gate import approve
            if not approve("shell_exec", f"Run shell command: {command[:120]}"):
                return "Execution Blocked: human approval denied/required (SALEHA_APPROVAL)."
            guard = SafetyGuard()
            safety = guard.evaluate(command)
            if not safety.is_safe:
                return f"Execution Blocked by Safety Guard: {safety.message}"
            import shlex
            import sys as _sys
            try:
                cmd_parts = command.split() if _sys.platform == 'win32' else shlex.split(command)
            except ValueError as e:
                return f"Command parse error: {e}"
            proc = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = proc.stdout + proc.stderr
            return output[:3000]

        self.register(ToolDefinition(
            name="shell_exec",
            description="Executes a controlled shell command passing safety checks.",
            parameters=[
                ToolParameter("command", "string", "Shell command to run.", required=True),
                ToolParameter("timeout", "integer", "Timeout in seconds.", required=False, default=15),
            ],
            handler=_shell_exec
        ))


class ToolCallingLoop:
    """Parses agent tool calls from response text and dispatches executions."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or global_tool_registry

    def parse_tool_call(self, text: str) -> Optional[ToolCall]:
        """Looks for tool call blocks formatted as ```tool_call {"tool": "name", "args": {...}} ```."""
        match = re.search(r"```(?:tool_call|json)\s*(\{.*?\})\s*```", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            tool_name = data.get("tool") or data.get("name")
            args = data.get("args") or data.get("arguments") or {}
            if tool_name and isinstance(args, dict):
                return ToolCall(tool_name=tool_name, arguments=args)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        return None

    def execute_and_format(self, text: str) -> Optional[ToolResult]:
        call = self.parse_tool_call(text)
        if not call:
            return None
        return self.registry.execute(call.tool_name, **call.arguments)


# Global tool registry instance
global_tool_registry = ToolRegistry()
