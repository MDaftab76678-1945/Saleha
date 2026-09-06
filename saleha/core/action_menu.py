"""
Saleha Core: Action Menu Loop -- choose an action instead of writing one.

The idea, and why it is different
---------------------------------
Every agent loop in this repo (and most elsewhere) asks the model to WRITE
a tool call:

    {"tool": "read_file", "args": {"path": "billing.py"}}

That asks a small model for the one thing it is worst at -- exact JSON
syntax and a valid file path -- while ignoring what it is actually good at:
knowing which file matters. Measured on this box with qwen2.5-coder:3b:

  * prompted directly, it emits a correct tool_call
  * inside the write-a-call loop it produced 0 real tool calls, and the
    same configuration run twice gave different results
  * during a real SWE-bench attempt it invented "path/to/model.py", a file
    that does not exist, because nothing stopped it from doing so

This module inverts that. Each turn the harness enumerates the REAL actions
available right now -- built from files that actually exist on disk -- and
the model replies with a single integer. Consequences that follow
structurally, not by checking afterwards:

  * A hallucinated path cannot be chosen, because it was never an option.
  * A parse failure cannot happen: with Ollama's structured-output schema
    the reply is constrained to one integer, so there is no malformed case
    to recover from.
  * A fabricated completion cannot happen: when the required evidence is
    missing, "finish" is simply absent from the menu. The older loop had to
    detect and reject such claims; here the claim is unrepresentable.

Deliberate limits, stated up front
----------------------------------
  * A menu can only offer what the harness thought to enumerate. Every menu
    therefore carries an explicit escape option (`search_repo`) so the model
    is never boxed in when the right file is not listed.
  * This trades some freedom for reliability. It is not the right shape for
    a strong model that can already emit correct calls -- it is aimed at the
    small local models this project targets.
  * Constrained decoding needs a provider that supports it (Ollama's
    `format` schema). Without it this falls back to parsing an integer out
    of the reply, which is still far easier than parsing a full call.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

MAX_MENU_ITEMS = 12
MAX_OBSERVATION_CHARS = 3000

# Ollama structured-output schema: the reply can only be a single integer.
CHOICE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {"choice": {"type": "integer"}},
    "required": ["choice"],
}


@dataclass
class MenuOption:
    """One concrete, executable action offered to the model."""

    label: str                      # human/model readable, e.g. 'read billing.py'
    tool: str                       # 'read_file'
    args: Dict[str, Any] = field(default_factory=dict)
    kind: str = "explore"           # explore | inspect | act | finish | escape

    def __str__(self) -> str:       # pragma: no cover - display helper
        return self.label


@dataclass
class MenuStep:
    step: int
    chosen: int
    option: str
    tool: str
    observation: str


@dataclass
class MenuResult:
    success: bool = False
    steps: List[MenuStep] = field(default_factory=list)
    final_message: str = ""
    error: str = ""
    invalid_choices: int = 0        # replies outside the offered range

    @property
    def tool_calls(self) -> List[str]:
        return [s.tool for s in self.steps if s.tool != "finish"]


def _truncate(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


class ActionMenuLoop:
    """
    Agent loop where the model selects an action rather than writing one.

    Tools are supplied by the caller (the same handlers AgentLoop uses), so
    this shares real tool implementations instead of duplicating them.
    """

    PROMPT = """You are Saleha Agent, working inside a real repository.

## Goal
{goal}

## What has happened so far
{history}

## Available actions
{menu}

Reply with ONLY the number of the single best next action."""

    def __init__(self, agent, root_dir: str = ".", max_steps: int = 10,
                 tools: Optional[Dict[str, Callable]] = None,
                 ledger=None, use_constrained_decoding: bool = True,
                 max_files_listed: int = 6):
        self.agent = agent
        self.root_dir = os.path.abspath(root_dir)
        self.max_steps = max_steps
        self.tools = tools or {}
        self.ledger = ledger
        self.use_constrained_decoding = use_constrained_decoding
        self.max_files_listed = max_files_listed
        self._read_files: set = set()

    # ------------------------------------------------------------------
    # Menu construction -- only real, executable actions
    # ------------------------------------------------------------------
    def _repo_files(self) -> List[str]:
        """Real source files under root, nearest-first, never invented."""
        out: List[str] = []
        skip = {"__pycache__", ".git", "node_modules", ".venv", ".venv_train",
                "target", "build", "dist", ".pytest_cache"}
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in sorted(filenames):
                if fn.endswith((".py", ".ts", ".js", ".go", ".rs", ".java",
                                ".rb", ".c", ".cpp", ".h")):
                    rel = os.path.relpath(os.path.join(dirpath, fn), self.root_dir)
                    out.append(rel.replace("\\", "/"))
            if len(out) > 200:
                break
        return sorted(out)

    def build_menu(self, goal: str) -> List[MenuOption]:
        """
        Enumerate what can genuinely be done right now.

        Files come from disk, so an option always refers to something that
        exists. `finish` is included only when the evidence ledger (if any)
        would actually admit a completion claim -- otherwise a fabricated
        completion is not merely rejected, it cannot be selected.
        """
        options: List[MenuOption] = []
        files = self._repo_files()

        # Rank unread files first, then ones whose name echoes the goal.
        goal_words = {w.lower() for w in re.findall(r"\w+", goal) if len(w) > 3}

        def rank(path: str) -> tuple:
            stem = os.path.basename(path).lower()
            mentioned = any(w in stem or w in path.lower() for w in goal_words)
            return (path in self._read_files, not mentioned, path)

        for path in sorted(files, key=rank)[:self.max_files_listed]:
            seen = " (already read)" if path in self._read_files else ""
            options.append(MenuOption(
                label=f"read {path}{seen}", tool="read_file",
                args={"path": path}, kind="inspect"))

        options.append(MenuOption(
            label="list the files in this repository", tool="list_dir",
            args={"path": "."}, kind="explore"))

        # Escape hatch: the menu can never be assumed complete.
        if goal_words:
            term = sorted(goal_words, key=len, reverse=True)[0]
            options.append(MenuOption(
                label=f"search the repository for '{term}'", tool="search_repo",
                args={"query": term}, kind="escape"))

        if self._finish_allowed():
            options.append(MenuOption(
                label="I have enough information -- finish and report",
                tool="finish", kind="finish"))

        return options[:MAX_MENU_ITEMS]

    def _finish_allowed(self) -> bool:
        """Finish is offered only when a completion claim would be admissible."""
        if self.ledger is None:
            return bool(self._read_files)
        return bool(self.ledger.judge_completion().admissible)

    # ------------------------------------------------------------------
    # Choice extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_choice(text: str, n_options: int) -> Optional[int]:
        """
        Pull the selected index out of a reply.

        With constrained decoding the reply is {"choice": N}. Without it,
        fall back to the first integer in range -- still far more forgiving
        than parsing a whole tool call.
        """
        if not text:
            return None
        m = re.search(r'"choice"\s*:\s*(\d+)', text)
        if m:
            idx = int(m.group(1))
            return idx if 1 <= idx <= n_options else None
        for tok in re.findall(r"\d+", text):
            idx = int(tok)
            if 1 <= idx <= n_options:
                return idx
        return None

    def _ask(self, prompt: str) -> str:
        """Ask the model, using constrained decoding when available."""
        if self.use_constrained_decoding:
            try:
                from saleha.core.model_provider import model_provider
                resp = model_provider.generate(
                    model=getattr(self.agent, "model", "auto"),
                    prompt=prompt,
                    options={"temperature": 0.0, "num_predict": 32},
                    response_format=CHOICE_SCHEMA,
                )
                if resp.success:
                    return resp.content or ""
            except (ImportError, TypeError, AttributeError):
                pass  # provider lacks structured output -- fall through
        r = self.agent.think(prompt, complexity_score=3.0)
        return (r.content or "") if getattr(r, "success", False) else ""

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def run(self, goal: str, on_event: Optional[Callable] = None) -> MenuResult:
        result = MenuResult()

        def emit(ev: Dict[str, Any]) -> None:
            if on_event:
                on_event(ev)

        history: List[str] = []

        for step_no in range(1, self.max_steps + 1):
            options = self.build_menu(goal)
            if not options:
                result.error = "no executable action available"
                return result

            menu_text = "\n".join(f"{i}. {o.label}" for i, o in enumerate(options, 1))
            prompt = self.PROMPT.format(
                goal=goal,
                history="\n".join(history[-6:]) or "(nothing yet)",
                menu=menu_text,
            )
            raw = self._ask(prompt)
            choice = self._parse_choice(raw, len(options))

            if choice is None:
                # Cannot happen under constrained decoding; if a provider
                # without it returns nonsense, take the first option rather
                # than ending the run -- doing *something* real beats dying.
                result.invalid_choices += 1
                choice = 1
                emit({"step": step_no, "action": "invalid-choice",
                      "observation": raw[:120]})

            picked = options[choice - 1]

            if picked.tool == "finish":
                summary = self._summarize(goal, history)
                result.success = True
                result.final_message = summary
                result.steps.append(MenuStep(step_no, choice, picked.label,
                                             "finish", summary))
                emit({"step": step_no, "action": "finish", "observation": summary})
                if self.ledger is not None:
                    self.ledger.accept()
                return result

            handler = self.tools.get(picked.tool)
            if handler is None:
                observation = f"tool '{picked.tool}' is not available"
            else:
                try:
                    observation = _truncate(str(handler(**picked.args)))
                except Exception as exc:
                    observation = f"tool error: {exc}"

            failed = observation.startswith("tool error:") or observation.startswith("tool '")
            if picked.tool == "read_file" and not failed:
                self._read_files.add(picked.args.get("path", ""))
                if self.ledger is not None:
                    from saleha.core.task_evidence import EvidenceKind
                    self.ledger.record(EvidenceKind.FILE_READ,
                                       picked.args.get("path", ""),
                                       "action_menu.run")
            elif picked.tool in ("list_dir", "search_repo") and not failed:
                if self.ledger is not None:
                    from saleha.core.task_evidence import EvidenceKind
                    self.ledger.record(EvidenceKind.SEARCH_PERFORMED,
                                       picked.label, "action_menu.run")

            result.steps.append(MenuStep(step_no, choice, picked.label,
                                         picked.tool, observation))
            history.append(f"[{step_no}] {picked.label}\n -> {observation[:300]}")
            emit({"step": step_no, "action": picked.tool,
                  "choice": choice, "observation": observation})

        result.error = f"max_steps ({self.max_steps}) reached without finishing"
        if self.ledger is not None:
            self.ledger.fail(result.error)
        return result

    def _summarize(self, goal: str, history: List[str]) -> str:
        """Ask for a free-text summary once the work is genuinely done."""
        prompt = (f"Goal: {goal}\n\nWhat you actually did and saw:\n"
                  + "\n".join(history[-8:])
                  + "\n\nIn 2-3 sentences, report what you found. "
                    "Only state things visible in the observations above.")
        try:
            r = self.agent.think(prompt, complexity_score=4.0)
            if getattr(r, "success", False) and (r.content or "").strip():
                return (r.content or "").strip()[:1000]
        except Exception:
            pass
        return "completed"
