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
        self._files_cache: Optional[List[str]] = None
        self._goal: str = ""   # set by run(); used by the edit tool's prompt

    # ------------------------------------------------------------------
    # Menu construction -- only real, executable actions
    # ------------------------------------------------------------------
    def _repo_files(self) -> List[str]:
        """
        Real source files under root, never invented.

        Scans the whole tree. An earlier version stopped at 200 files, which
        on a real repo truncated the walk alphabetically -- on SWE-bench
        astropy-12907 it stopped inside astropy/config/ and never reached
        astropy/modeling/separable.py, the one file the fix needed. The file
        existed on disk and the goal named it outright, yet it could never
        be offered. Capping discovery is the wrong place to bound cost; the
        menu itself is already capped (MAX_MENU_ITEMS), and ranking decides
        what makes it in.
        """
        if self._files_cache is not None:
            return self._files_cache
        out: List[str] = []
        skip = {"__pycache__", ".git", "node_modules", ".venv", ".venv_train",
                "target", "build", "dist", ".pytest_cache", ".tox", ".eggs"}
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                if fn.endswith((".py", ".ts", ".js", ".go", ".rs", ".java",
                                ".rb", ".c", ".cpp", ".h")):
                    rel = os.path.relpath(os.path.join(dirpath, fn), self.root_dir)
                    out.append(rel.replace("\\", "/"))
        self._files_cache = sorted(out)
        return self._files_cache

    @staticmethod
    def paths_named_in(goal: str) -> List[str]:
        """
        Repo paths the goal text itself points at.

        Measured need: on SWE-bench astropy-12907 the fix lives in
        astropy/modeling/separable.py, and the problem statement literally
        contains `from astropy.modeling.separable import separability_matrix`
        -- yet an alphabetical menu offered only astropy/config/*, so the
        one file that mattered could never be chosen. Dotted module paths
        and explicit file paths in the goal are the strongest available
        signal and must outrank everything else.
        """
        found: List[str] = []
        # Explicit file paths: astropy/modeling/separable.py
        for m in re.findall(r"[\w./\\-]+\.(?:py|ts|js|go|rs|java|rb|c|cpp|h)\b", goal):
            found.append(m.replace("\\", "/"))
        # Dotted module paths from import statements -> file path
        for m in re.findall(r"(?:from|import)\s+([\w.]+)", goal):
            if "." in m:
                found.append(m.replace(".", "/") + ".py")
        # Dedupe, keep order (earliest mention first).
        seen, out = set(), []
        for f in found:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

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
        file_set = set(files)

        # Files the goal names outright come first -- see paths_named_in().
        named = [p for p in self.paths_named_in(goal) if p in file_set]
        # Also accept a suffix match, since a goal may name a partial path.
        if not named:
            for cand in self.paths_named_in(goal):
                tail = cand.split("/")[-1]
                named += [p for p in files if p.endswith("/" + tail) or p == tail]

        # Rank unread files first, then ones whose name echoes the goal.
        goal_words = {w.lower() for w in re.findall(r"\w+", goal) if len(w) > 3}

        def rank(path: str) -> tuple:
            stem = os.path.basename(path).lower()
            mentioned = any(w in stem or w in path.lower() for w in goal_words)
            return (path in self._read_files, not mentioned, path)

        # Drop files already read. Measured on SWE-bench astropy-14182: with
        # already-read files still listed, the model re-picked the same two
        # files for 6 of its 12 turns, burning the whole budget on repeats.
        # Re-reading is never the useful next action here, so remove the
        # option rather than relying on the model to avoid it.
        ordered = [p for p in (named + [p for p in sorted(files, key=rank)
                                        if p not in named])
                   if p not in self._read_files]
        for path in ordered[:self.max_files_listed]:
            hint = " <- named in the task" if path in named else ""
            options.append(MenuOption(
                label=f"read {path}{hint}", tool="read_file",
                args={"path": path}, kind="inspect"))

        # Once a file has actually been read, offer editing it. Without this
        # the menu can only ever explore: a real SWE-bench run read 12 real
        # files and still produced an empty patch, because no option existed
        # that could change anything. `propose_edit` is offered per already-
        # read file so the target is always something the model has seen.
        if "propose_edit" in self.tools:
            for path in sorted(self._read_files)[:3]:
                options.append(MenuOption(
                    label=f"edit {path} to fix the problem", tool="propose_edit",
                    args={"path": path}, kind="act"))

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
        self._goal = goal

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

    def make_edit_tool(self, read_file: Callable, patch_file: Callable) -> Callable:
        """
        Build a `propose_edit` handler for the menu.

        Editing is the one action a menu cannot pre-enumerate -- the harness
        cannot know the replacement text in advance. So this keeps the menu's
        guarantee where it matters (WHICH file is chosen from real, already-
        read files) while asking the model for the edit itself in a narrow,
        single-purpose prompt: given this file's real contents and the goal,
        emit one search/replace pair. The search string is then verified to
        actually occur in the file before anything is written, so a
        hallucinated snippet fails loudly instead of corrupting the file.
        """
        def propose_edit(path: str = "") -> str:
            content = str(read_file(path=path))
            if content.startswith("no such file") or not content.strip():
                return f"cannot edit {path}: unreadable"

            prompt = (
                f"File: {path}\n\n{content[:6000]}\n\n"
                f"Task: {self._goal}\n\n"
                "Reply with ONLY a JSON object giving one exact edit:\n"
                '{"search": "<exact text copied from the file above>", '
                '"replace": "<the corrected text>"}\n'
                "The search text must appear in the file EXACTLY as written above."
            )
            try:
                r = self.agent.think(prompt, complexity_score=7.0)
                raw = (r.content or "") if getattr(r, "success", False) else ""
            except Exception as exc:
                return f"edit generation failed: {exc}"

            import json as _json
            data = None
            for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL):
                try:
                    cand = _json.loads(m.group(0))
                except _json.JSONDecodeError:
                    continue
                if isinstance(cand, dict) and "search" in cand and "replace" in cand:
                    data = cand
                    break
            if not data:
                return "no usable {search, replace} edit was produced"

            search, replace = str(data["search"]), str(data["replace"])
            if search not in content:
                # The model invented text that is not in the file. Say so
                # plainly rather than writing something unverified.
                return ("edit rejected: the search text does not appear in "
                        f"{path}. Copy it exactly from the file.")
            if search == replace:
                return "edit rejected: search and replace are identical"

            out = str(patch_file(path=path, search=search, replace=replace))
            if self.ledger is not None and "error" not in out.lower():
                from saleha.core.task_evidence import EvidenceKind
                self.ledger.record(EvidenceKind.FILE_MODIFIED, path,
                                   "action_menu.propose_edit")
            return out

        return propose_edit

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
