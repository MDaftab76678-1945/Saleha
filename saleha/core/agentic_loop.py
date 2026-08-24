"""
Saleha Core: Agentic Tool-Use Loop (ReAct) -- v1.1 keystone

Ab tak Saleha FIXED-stage pipeline chalata tha (Plan->Code->Test...). Ye
advanced mode hai jahan model KHUD decide karta hai agla kadam kya ho:

    think -> tool call -> observation -> think -> ... -> finish

Available tools (repo-sandboxed, read-only by default):
    list_dir(path)            -- directory entries
    read_file(path)           -- file content (truncated)
    search_repo(pattern)      -- regex search across code files
    run_code(code)            -- sandboxed execution (Docker policy applies)
    write_file(path, content) -- OPTIONAL (allow_write=True + approval gate)

Termination: model ```json {"finish": "<summary>"}``` emit kare, ya
max_steps exhaust. Har step on_event callback se stream hota hai (Web
Studio/CLI live view ke liye).

Security:
- Saare paths root_dir ke andar force (traversal blocked)
- run_code CodeExecutor policy follow karta hai (SALEHA_SANDBOX)
- write_file approval_gate se gated (SALEHA_APPROVAL=dangerous/always)
"""

import os
import re
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.core.path_utils import safe_relpath

MAX_OBSERVATION_CHARS = 3000
MAX_FILE_READ_CHARS = 4000
_MAX_SEARCH_HITS = 30

_FINISH_RE = re.compile(r"```(?:json)?\s*(\{.*?\"finish\".*?\})\s*```", re.DOTALL)


@dataclass
class LoopStep:
    step: int
    action: str                 # tool name ya "finish"
    args_preview: str
    observation: str


@dataclass
class LoopResult:
    success: bool = False
    steps: List[LoopStep] = field(default_factory=list)
    final_message: str = ""
    error: str = ""             # max_steps / infra failure reason

    @property
    def transcript(self) -> str:
        lines = []
        for s in self.steps:
            lines.append(f"[{s.step}] {s.action}({s.args_preview})")
            obs = s.observation[:400].replace("\n", " ⏎ ")
            lines.append(f"    -> {obs}")
        return "\n".join(lines)


def _truncate(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


class AgentLoop:
    """Model-driven autonomous investigation/experiment loop over a repo."""

    SYSTEM_PROMPT = """You are Saleha Agent, an autonomous software engineer working inside a repository.

Reply with EXACTLY ONE block each turn:

To use a tool:
```tool_call
{"tool": "<tool_name>", "args": {...}}
```

Tools available: {tool_names}

When the goal is achieved, finish:
```json
{"finish": "<concise summary of what you found/did>"}
```

Never invent tool outputs. One block per reply. Be efficient."""

    def __init__(self, agent: BaseAgent, root_dir: str = ".",
                 max_steps: int = 12, allow_write: bool = False,
                 code_executor=None,
                 allowed_tools: Optional[List[str]] = None):
        self.agent = agent
        self.root_dir = os.path.abspath(root_dir)
        self.max_steps = max_steps
        self.allow_write = allow_write
        # Profile-driven tool restriction (v1.5): agar diya gaya to sirf ye
        # tools available honge (intersection with built-ins).
        self.allowed_tools = set(allowed_tools) if allowed_tools else None
        self._executor = code_executor  # lazy init in _tool_run_code

    # ------------------------------------------------------------------
    # Path safety
    # ------------------------------------------------------------------
    def _safe_path(self, rel: str) -> Optional[str]:
        if not rel:
            return None
        rel = rel.strip().replace("\\", "/")
        abs_p = os.path.abspath(os.path.join(self.root_dir, rel))
        if not abs_p.startswith(self.root_dir + os.sep):
            return None
        return abs_p

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------
    SKIP_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", ".saleha"}

    def _tool_list_dir(self, path: str = "") -> str:
        abs_p = self._safe_path(path) or self.root_dir
        if not os.path.isdir(abs_p):
            return f"not a directory: {path}"
        entries = []
        for name in sorted(os.listdir(abs_p))[:200]:
            full = os.path.join(abs_p, name)
            kind = "dir " if os.path.isdir(full) else "file"
            size = "" if kind == "dir " else f" {os.path.getsize(full)}B"
            entries.append(f"{kind} {name}{size}")
        return "\n".join(entries) or "(empty)"

    def _tool_read_file(self, path: str) -> str:
        abs_p = self._safe_path(path)
        if not abs_p or not os.path.isfile(abs_p):
            return f"no such file: {path}"
        try:
            with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_FILE_READ_CHARS + 1)
        except OSError as err:
            return f"read error: {err}"
        if len(content) > MAX_FILE_READ_CHARS:
            content = content[:MAX_FILE_READ_CHARS] + "\n...[truncated]"
        return content

    def _tool_search_repo(self, pattern: str) -> str:
        try:
            rx = re.compile(pattern)
        except re.error as err:
            return f"invalid regex: {err}"
        hits: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in self.SKIP_DIRS]
            for fname in filenames:
                if len(hits) >= _MAX_SEARCH_HITS:
                    return "\n".join(hits) + f"\n[stopped at {_MAX_SEARCH_HITS} hits]"
                full = os.path.join(dirpath, fname)
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if rx.search(line):
                                rel = safe_relpath(full, self.root_dir)
                                hits.append(f"{rel}:{i}: {line.strip()[:160]}")
                                break  # ek file se 1 hit kaafi (breadth first)
                except OSError:
                    continue
        return "\n".join(hits) or "no matches"

    def _tool_run_code(self, code: str) -> str:
        from saleha.core.code_executor import CodeExecutor
        if self._executor is None:
            self._executor = CodeExecutor(timeout=15)
        res = self._executor.execute(code, timeout=15)
        if res.blocked:
            return f"BLOCKED by safety layer: {res.block_reason}"
        out = f"exit={res.exit_code}\nstdout: {_truncate(res.output, 1200)}"
        if res.error:
            out += f"\nstderr: {_truncate(res.error, 800)}"
        return out

    def _tool_write_file(self, path: str, content: str) -> str:
        if not self.allow_write:
            return "BLOCKED: write tool disabled (enable allow_write=True)"
        from saleha.core.approval_gate import approve
        abs_p = self._safe_path(path)
        if not abs_p:
            return f"path traversal blocked: {path}"
        if not approve("file_write", f"{path} ({len(content)} chars)"):
            return "BLOCKED: human approval denied/required."
        try:
            os.makedirs(os.path.dirname(abs_p), exist_ok=True)
            with open(abs_p, "w", encoding="utf-8") as f:
                f.write(content)
            return f"written: {path} ({len(content)} chars)"
        except OSError as err:
            return f"write error: {err}"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self, goal: str, on_event: Optional[Callable[[Dict], None]] = None) -> LoopResult:
        result = LoopResult()

        def emit(ev: Dict):
            if on_event:
                try:
                    on_event(ev)
                except Exception:
                    pass

        tools: Dict[str, Callable] = {
            "list_dir": self._tool_list_dir,
            "read_file": self._tool_read_file,
            "search_repo": self._tool_search_repo,
            "run_code": self._tool_run_code,
            # Hamesha registered -- handler khud allow_write check karta hai,
            # taaki model ko clear "BLOCKED" observation mile (silent absence se behtar)
            "write_file": self._tool_write_file,
        }

        # Profile-driven restriction: allowed_tools diya gaya to intersection
        # use karo (khali result par sab wapas -- dead-end se bachne ke liye).
        if self.allowed_tools:
            filtered = {k: v for k, v in tools.items() if k in self.allowed_tools}
            if filtered:
                tools = filtered

        system = self.SYSTEM_PROMPT.replace("{tool_names}", ", ".join(tools))
        transcript_parts: List[str] = []

        for step_no in range(1, self.max_steps + 1):
            prompt = (
                f"{system}\n\n## Goal\n{goal}\n\n"
                f"## Action-Observation History (steps {len(transcript_parts)})\n"
                + ("\n".join(transcript_parts[-6:]) or "(none yet)")
            )
            resp: AgentResponse = self.agent.think(prompt, complexity_score=7.0)
            if not resp.success:
                result.error = f"LLM error at step {step_no}: {resp.error_message}"
                emit({"step": step_no, "action": "error", "observation": result.error})
                return result

            # Finish check pehle
            fin = _FINISH_RE.search(resp.content)
            if fin:
                try:
                    summary = str(json.loads(fin.group(1)).get("finish", ""))
                except json.JSONDecodeError:
                    summary = fin.group(1)[:500]
                result.success = True
                result.final_message = summary or "done"
                result.steps.append(LoopStep(step_no, "finish", "", result.final_message))
                emit({"step": step_no, "action": "finish", "observation": result.final_message})
                return result

            # Tool call parse (```tool_call {...}``` format)
            call = self._parse_call(resp.content)
            if call is None:
                result.error = f"step {step_no}: model returned no tool_call/finish block"
                emit({"step": step_no, "action": "parse-error",
                      "observation": resp.content[:200]})
                return result

            tool_name, args = call
            handler = tools.get(tool_name)
            if handler is None:
                observation = f"unknown tool '{tool_name}'. Available: {', '.join(tools)}"
            else:
                try:
                    observation = _truncate(str(handler(**args)))
                except TypeError as terr:
                    observation = f"bad args for {tool_name}: {terr}"
                except Exception as exc:
                    observation = f"tool error: {exc}"

            args_preview = json.dumps(args)[:120]
            result.steps.append(LoopStep(step_no, tool_name, args_preview, observation))
            emit({"step": step_no, "action": tool_name,
                  "args": args, "observation": observation})
            transcript_parts.append(
                f"[step {step_no}] {tool_name}({args_preview})\nOBSERVATION: {observation}"
            )

        result.error = f"max_steps ({self.max_steps}) exhausted without finish"
        return result

    @staticmethod
    def _parse_call(text: str) -> Optional[Tuple[str, Dict]]:
        m = re.search(r"```(?:tool_call)?\s*(\{.*?\})\s*```", text or "", re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
        name = data.get("tool") or data.get("name")
        args = data.get("args") or data.get("arguments") or {}
        if name and isinstance(args, dict):
            return str(name), args
        return None
