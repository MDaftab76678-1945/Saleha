"""
Saleha Workflow Engine: Core Nodes & Abstractions.

Defines the fundamental node contracts, typed ports, and built-in node implementations
for the SalehaFlow autonomous workflow system.
"""

from __future__ import annotations

import json
import secrets
import sys
import tempfile
import time
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class NodeStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    HEALED = "HEALED"


@dataclass
class WorkflowExecutionContext:
    """
    Shared runtime execution context for a workflow run.
    Provides data piping, Global Workspace (Blackboard), and telemetry logging.
    """
    workflow_id: str
    execution_id: str
    data_pipes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blackboard: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    event_listeners: List[Callable[[str, Dict[str, Any]], None]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set_output(self, node_id: str, data: Dict[str, Any]) -> None:
        self.data_pipes[node_id] = data

    def get_output(self, node_id: str) -> Dict[str, Any]:
        return self.data_pipes.get(node_id, {})

    def publish_blackboard(self, key: str, value: Any) -> None:
        self.blackboard[key] = value

    def read_blackboard(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, default)

    def log(self, message: str) -> None:
        entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self.logs.append(entry)

    def emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        for listener in self.event_listeners:
            try:
                listener(event_type, payload)
            except Exception:
                pass


_RESTRICTED_BUILTINS = (
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "len",
    "list", "map", "max", "min", "range", "round", "set", "str", "sum", "tuple", "zip",
)


def run_code_isolated(
    code: str,
    inputs: Dict[str, Any],
    timeout_sec: float = 10.0,
    memory_limit_mb: int = 256,
    restricted_builtins: bool = False,
) -> Dict[str, Any]:
    """Runs a node snippet in a job-object subprocess; `inputs`/`outputs` travel as JSON."""
    from saleha.core.windows_job_sandbox import WindowsJobSandbox

    marker = "__saleha_node_outputs__" + secrets.token_hex(8)
    builtins_expr = (
        f"{{n: getattr(builtins, n) for n in {_RESTRICTED_BUILTINS!r}}}"
        if restricted_builtins else "builtins"
    )
    harness = "\n".join([
        "import builtins, json",
        f"_scope = {{'inputs': json.loads({json.dumps(inputs, default=str)!r}), 'outputs': {{}}}}",
        f"exec(compile({code!r}, '<workflow_node>', 'exec'), {{'__builtins__': {builtins_expr}}}, _scope)",
        "_out = _scope.get('outputs', {})",
        "_out = _out if isinstance(_out, dict) else {'result': _out}",
        f"print({marker!r} + json.dumps(_out, default=str))",
    ]) + "\n"
    sandbox = WindowsJobSandbox(memory_limit_mb=memory_limit_mb, timeout_ms=int(timeout_sec * 1000))
    with tempfile.TemporaryDirectory(prefix="saleha_node_", ignore_cleanup_errors=True) as tmp:
        script = Path(tmp) / "node.py"
        script.write_text(harness, encoding="utf-8")
        res = sandbox.run_isolated([sys.executable, str(script)], timeout_sec=timeout_sec, cwd=tmp)
    for line in reversed(res.output.splitlines()):
        if line.startswith(marker):
            if not res.passed:
                break
            return json.loads(line[len(marker):])
    detail = res.error.strip().splitlines()[-1] if res.error.strip() else f"exit code {res.exit_code}"
    raise RuntimeError(f"Node code failed in sandbox: {detail}")


class WorkflowNode:
    """
    Base contract for all workflow nodes in SalehaFlow.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        node_type: str = "generic",
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.id = node_id
        self.title = title
        self.node_type = node_type
        self.depends_on: List[str] = depends_on or []
        self.config: Dict[str, Any] = config or {}
        self.status: NodeStatus = NodeStatus.PENDING
        self.error: str = ""
        self.duration_ms: float = 0.0
        self.inputs: Dict[str, Any] = {}
        self.outputs: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}

    def resolve_inputs(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        """
        Gathers output payloads from all upstream dependencies into a merged dictionary.
        """
        resolved: Dict[str, Any] = {}
        for dep_id in self.depends_on:
            dep_out = context.get_output(dep_id)
            resolved[dep_id] = dep_out
            if isinstance(dep_out, dict):
                for k, v in dep_out.items():
                    if k not in resolved:
                        resolved[k] = v
        return resolved

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        """
        Executes node logic and returns an output dictionary.
        Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.node_type,
            "depends_on": self.depends_on,
            "config": self.config,
            "status": self.status.value,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class ActionNode(WorkflowNode):
    """
    Executes a custom Python callable action.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        action_fn: Callable[[Dict[str, Any], WorkflowExecutionContext], Dict[str, Any]],
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type="action", depends_on=depends_on, config=config)
        self.action_fn = action_fn

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        inputs = self.resolve_inputs(context)
        return self.action_fn(inputs, context)


class CodeNode(WorkflowNode):
    """
    Runs a Python snippet in a job-object subprocess. The snippet reads the
    JSON-serialisable `inputs` dict and assigns `outputs`; it has no access to
    the workflow context.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        code_str: str,
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type="code", depends_on=depends_on, config=config)
        self.code_str = code_str

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        inputs = self.resolve_inputs(context)
        return run_code_isolated(
            self.code_str, inputs, timeout_sec=float(self.config.get("timeout_sec", 10.0))
        )


class HTTPNode(WorkflowNode):
    """
    Executes an HTTP request with automatic JSON decoding and payload extraction.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        timeout: float = 15.0,
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type="http", depends_on=depends_on, config=config)
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.body = body
        self.timeout = timeout

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        inputs = self.resolve_inputs(context)
        # Template variable replacement in URL if applicable
        resolved_url = self.url
        for k, v in inputs.items():
            if isinstance(v, (str, int, float)):
                placeholder = f"{{{k}}}"
                if placeholder in resolved_url:
                    resolved_url = resolved_url.replace(placeholder, str(v))

        data_bytes = None
        if self.body is not None:
            if isinstance(self.body, (dict, list)):
                data_bytes = json.dumps(self.body).encode("utf-8")
                self.headers.setdefault("Content-Type", "application/json")
            elif isinstance(self.body, str):
                data_bytes = self.body.encode("utf-8")

        req = urllib.request.Request(resolved_url, data=data_bytes, headers=self.headers, method=self.method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                raw_bytes = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                
                parsed_body: Any = raw_bytes.decode("utf-8", errors="replace")
                if "application/json" in content_type:
                    try:
                        parsed_body = json.loads(parsed_body)
                    except Exception:
                        pass

                return {
                    "status_code": status_code,
                    "headers": dict(resp.headers),
                    "data": parsed_body,
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} Error: {error_body}") from e
        except Exception as e:
            raise RuntimeError(f"HTTP Connection Failed: {str(e)}") from e


class ConditionNode(WorkflowNode):
    """
    Evaluates a boolean condition and outputs `verdict` / `branch`.
    The engine does not route on it: every downstream node still runs, and
    must read `verdict` itself.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        condition_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        expression: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type="condition", depends_on=depends_on, config=config)
        self.condition_fn = condition_fn
        self.expression = expression

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        inputs = self.resolve_inputs(context)
        verdict = False
        if self.condition_fn:
            verdict = self.condition_fn(inputs)
        elif self.expression:
            # Safe evaluation of boolean expression
            verdict = bool(eval(self.expression, {"__builtins__": {}}, {"inputs": inputs, **inputs}))  # saleha: allow-exec

        return {
            "verdict": verdict,
            "branch": "true" if verdict else "false",
        }


class AgentNode(WorkflowNode):
    """
    Executes a reasoning, planning, or code synthesis step using Saleha's BaseAgent
    or local model with structured schema constraints.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        prompt_template: str,
        agent_role: str = "WorkflowAgent",
        model: str = "auto",
        structured_schema: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type="agent", depends_on=depends_on, config=config)
        self.prompt_template = prompt_template
        self.agent_role = agent_role
        self.model = model
        self.structured_schema = structured_schema

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        from saleha.agents.base_agent import BaseAgent
        inputs = self.resolve_inputs(context)

        # Template substitution
        prompt = self.prompt_template
        for k, v in inputs.items():
            if isinstance(v, (str, int, float)):
                prompt = prompt.replace(f"{{{k}}}", str(v))
            elif isinstance(v, dict):
                prompt = prompt.replace(f"{{{k}}}", json.dumps(v))

        agent = BaseAgent(role=self.agent_role, model=self.model)
        resp = agent.think(prompt)

        if not resp.success:
            raise RuntimeError(f"Agent reasoning failed: {getattr(resp, 'error', 'Unknown agent error')}")

        content = resp.content or ""
        parsed_json: Optional[Dict[str, Any]] = None
        # Attempt extracting JSON block if structured
        if "```json" in content:
            try:
                block = content.split("```json")[1].split("```")[0].strip()
                parsed_json = json.loads(block)
            except Exception:
                pass
        elif content.strip().startswith("{") and content.strip().endswith("}"):
            try:
                parsed_json = json.loads(content.strip())
            except Exception:
                pass

        return {
            "content": content,
            "structured_data": parsed_json,
            "role": self.agent_role,
        }
