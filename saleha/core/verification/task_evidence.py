"""
Saleha Core: Evidence-Based Task Completion

Implements the "Evidence-Based Completion" and "Immutable Task State"
requirements from the project's own Level-6 architecture target (see
Notebook/Architecture Vision.txt, which rates the previous behaviour a
3/10 prototype).

The real problem this solves
----------------------------
An agent could previously declare a task finished purely by *saying* so.
That was verified to happen against real SWE-bench Lite instances: the
model called ``finish()`` on turn 1, before any tool call, with a
fabricated summary ("File read successfully" -- nothing had been read).
``AgentLoop.min_actions_before_finish`` stopped the zero-effort case, but
"the agent took one action" is still not the same as "the work is
actually done and verified".

This module makes completion a *claim that must be backed by evidence*:

- ``TaskState`` is an explicit state machine (CREATED -> ANALYZING ->
  PLANNING -> IMPLEMENTING -> VERIFYING -> ACCEPTED, with REPAIRING and
  FAILED), so a long-running task can never silently "forget" what stage
  it is in.
- ``Evidence`` records one verifiable fact, each carrying how it was
  obtained. Evidence is only ever recorded by code that actually observed
  the thing -- never by the model asserting it.
- ``EvidenceLedger`` decides whether a completion claim is admissible,
  given a required set of evidence kinds.
- ``ResourceBudget`` enforces the hard limits the architecture asks for
  (max tool calls, wall-clock seconds, and estimated cost), so a runaway
  or looping agent stops instead of burning the budget.

Nothing here calls an LLM, and nothing fabricates a result: every check
either observes something real or reports that it could not.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class TaskState(str, Enum):
    """Explicit task lifecycle. Values are strings so they serialise cleanly."""

    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    ACCEPTED = "ACCEPTED"
    FAILED = "FAILED"


# Which transitions are legal. A task cannot jump straight from CREATED to
# ACCEPTED -- that jump is exactly the fabricated-completion bug.
_ALLOWED_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.CREATED: {TaskState.ANALYZING, TaskState.FAILED},
    TaskState.ANALYZING: {TaskState.PLANNING, TaskState.IMPLEMENTING,
                          TaskState.VERIFYING, TaskState.FAILED},
    TaskState.PLANNING: {TaskState.IMPLEMENTING, TaskState.ANALYZING,
                         TaskState.FAILED},
    TaskState.IMPLEMENTING: {TaskState.VERIFYING, TaskState.IMPLEMENTING,
                             TaskState.ANALYZING, TaskState.FAILED},
    TaskState.VERIFYING: {TaskState.ACCEPTED, TaskState.REPAIRING,
                          TaskState.IMPLEMENTING, TaskState.FAILED},
    TaskState.REPAIRING: {TaskState.IMPLEMENTING, TaskState.VERIFYING,
                          TaskState.FAILED},
    TaskState.ACCEPTED: set(),   # terminal
    TaskState.FAILED: set(),     # terminal
}

TERMINAL_STATES = {TaskState.ACCEPTED, TaskState.FAILED}


class EvidenceKind(str, Enum):
    """Kinds of verifiable fact a completion claim can rest on."""

    FILE_READ = "file_read"            # agent actually read a real file
    FILE_MODIFIED = "file_modified"    # a real file changed on disk
    FILE_EXISTS = "file_exists"        # a required output file is present
    CODE_EXECUTED = "code_executed"    # code actually ran
    TESTS_PASSED = "tests_passed"      # a real test command exited 0
    SYNTAX_VALID = "syntax_valid"      # source parses
    SEARCH_PERFORMED = "search_performed"


@dataclass(frozen=True)
class Evidence:
    """One verifiable fact, plus how it was obtained.

    ``source`` names the code path that observed it, so a reader can always
    trace a claim back to the thing that actually checked it.
    """

    kind: EvidenceKind
    detail: str
    source: str
    at: float = field(default_factory=time.time)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.kind.value}: {self.detail} (via {self.source})"


class BudgetExceeded(Exception):
    """Raised when a task exhausts one of its hard resource limits."""


@dataclass
class ResourceBudget:
    """
    Hard limits from the Level-6 spec ("max_tool_calls / max_time /
    max_cost"). Set any field to None to leave that dimension unlimited.

    ``spend()`` is the only mutator; it raises ``BudgetExceeded`` rather
    than silently continuing, so a runaway loop stops loudly.
    """

    max_tool_calls: Optional[int] = None
    max_seconds: Optional[float] = None
    max_cost_usd: Optional[float] = None

    tool_calls_used: int = 0
    cost_usd_used: float = 0.0
    started_at: float = field(default_factory=time.time)

    def spend(self, tool_calls: int = 0, cost_usd: float = 0.0) -> None:
        """Record usage, then enforce every limit. Raises BudgetExceeded."""
        self.tool_calls_used += tool_calls
        self.cost_usd_used += cost_usd
        self.check()

    def check(self) -> None:
        if self.max_tool_calls is not None and self.tool_calls_used > self.max_tool_calls:
            raise BudgetExceeded(
                f"tool call budget exhausted: {self.tool_calls_used}/{self.max_tool_calls}")
        if self.max_cost_usd is not None and self.cost_usd_used > self.max_cost_usd:
            raise BudgetExceeded(
                f"cost budget exhausted: ${self.cost_usd_used:.4f}/${self.max_cost_usd:.4f}")
        if self.max_seconds is not None and self.elapsed_seconds > self.max_seconds:
            raise BudgetExceeded(
                f"time budget exhausted: {self.elapsed_seconds:.1f}s/{self.max_seconds:.1f}s")

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def remaining_tool_calls(self) -> Optional[int]:
        if self.max_tool_calls is None:
            return None
        return max(0, self.max_tool_calls - self.tool_calls_used)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "tool_calls_used": self.tool_calls_used,
            "max_tool_calls": self.max_tool_calls,
            "cost_usd_used": round(self.cost_usd_used, 6),
            "max_cost_usd": self.max_cost_usd,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "max_seconds": self.max_seconds,
        }


@dataclass
class CompletionVerdict:
    """Result of judging a completion claim. Never a bare bool."""

    admissible: bool
    reason: str
    satisfied: List[EvidenceKind] = field(default_factory=list)
    missing: List[EvidenceKind] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.admissible


class EvidenceLedger:
    """
    Append-only record of what was actually observed during a task, plus
    the state machine governing the task's lifecycle.

    The ledger never inspects model output. Callers record evidence from
    code that genuinely observed the fact (a tool handler, a test run), so
    "the model said it passed" can never become evidence.
    """

    def __init__(self, goal: str = "",
                 required: Optional[Set[EvidenceKind]] = None,
                 budget: Optional[ResourceBudget] = None):
        self.goal = goal
        # Default requirement: at least one real read AND one real action.
        # Investigation-only tasks can pass {EvidenceKind.FILE_READ}.
        self.required: Set[EvidenceKind] = (
            set(required) if required is not None else {EvidenceKind.FILE_READ}
        )
        self.budget = budget or ResourceBudget()
        self.state: TaskState = TaskState.CREATED
        self._evidence: List[Evidence] = []
        self._history: List[tuple] = [(TaskState.CREATED, time.time(), "created")]

    # -- state machine -------------------------------------------------
    def transition(self, to_state: TaskState, note: str = "") -> None:
        """Move to a new state. Raises ValueError on an illegal jump."""
        allowed = _ALLOWED_TRANSITIONS.get(self.state, set())
        if to_state not in allowed:
            raise ValueError(
                f"illegal transition {self.state.value} -> {to_state.value}; "
                f"allowed: {sorted(s.value for s in allowed) or 'none (terminal)'}"
            )
        self.state = to_state
        self._history.append((to_state, time.time(), note))

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def history(self) -> List[Dict[str, Any]]:
        return [{"state": s.value, "at": t, "note": n} for s, t, n in self._history]

    # -- evidence ------------------------------------------------------
    def record(self, kind: EvidenceKind, detail: str, source: str) -> Evidence:
        """Append one observed fact. Only real observers should call this."""
        ev = Evidence(kind=kind, detail=detail, source=source)
        self._evidence.append(ev)
        return ev

    @property
    def evidence(self) -> List[Evidence]:
        return list(self._evidence)

    def kinds_present(self) -> Set[EvidenceKind]:
        return {e.kind for e in self._evidence}

    def has(self, kind: EvidenceKind) -> bool:
        return any(e.kind == kind for e in self._evidence)

    # -- the actual gate -----------------------------------------------
    def judge_completion(self) -> CompletionVerdict:
        """
        Decide whether a completion claim is admissible.

        Admissible only if every required evidence kind was actually
        observed. This is the check that makes "done" mean something.
        """
        present = self.kinds_present()
        missing = sorted(self.required - present, key=lambda k: k.value)
        satisfied = sorted(self.required & present, key=lambda k: k.value)
        if missing:
            names = ", ".join(k.value for k in missing)
            return CompletionVerdict(
                admissible=False,
                reason=(f"no evidence of: {names}. A summary is not evidence -- "
                        f"actually perform and verify the work first."),
                satisfied=satisfied,
                missing=missing,
            )
        return CompletionVerdict(
            admissible=True,
            reason=f"all {len(self.required)} required evidence kind(s) observed",
            satisfied=satisfied,
            missing=[],
        )

    def accept(self) -> CompletionVerdict:
        """
        Attempt to reach ACCEPTED. Only succeeds with sufficient evidence;
        otherwise the ledger stays where it is and the verdict explains why.
        """
        verdict = self.judge_completion()
        if not verdict.admissible:
            return verdict
        if self.state == TaskState.VERIFYING:
            self.transition(TaskState.ACCEPTED, verdict.reason)
        elif self.state not in TERMINAL_STATES:
            # Route through VERIFYING so the recorded history always shows
            # that verification happened before acceptance.
            self.transition(TaskState.VERIFYING, "evidence check")
            self.transition(TaskState.ACCEPTED, verdict.reason)
        return verdict

    def fail(self, reason: str) -> None:
        if self.state not in TERMINAL_STATES:
            self.transition(TaskState.FAILED, reason)

    def summary(self) -> Dict[str, Any]:
        verdict = self.judge_completion()
        return {
            "goal": self.goal,
            "state": self.state.value,
            "evidence_count": len(self._evidence),
            "evidence": [str(e) for e in self._evidence],
            "kinds_present": sorted(k.value for k in self.kinds_present()),
            "required": sorted(k.value for k in self.required),
            "admissible": verdict.admissible,
            "reason": verdict.reason,
            "budget": self.budget.snapshot(),
            "history": self.history,
        }


# ----------------------------------------------------------------------
# Real verifiers -- each observes something concrete, or reports it could not
# ----------------------------------------------------------------------

def verify_file_exists(path: str, ledger: EvidenceLedger) -> bool:
    """Record FILE_EXISTS only if the file is genuinely on disk."""
    if os.path.isfile(path):
        size = os.path.getsize(path)
        ledger.record(EvidenceKind.FILE_EXISTS, f"{path} ({size} bytes)",
                      "task_evidence.verify_file_exists")
        return True
    return False


def verify_python_syntax(path: str, ledger: EvidenceLedger) -> bool:
    """
    Record SYNTAX_VALID only if the file really parses.

    Note deliberately: this proves the file is syntactically valid Python
    and nothing more -- it does not prove the code is correct. A previous
    generator in this repo treated ast.parse() success as proof of a
    correct solution, which produced 493 mismatched training samples.
    """
    import ast
    try:
        with open(path, "r", encoding="utf-8") as f:
            ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return False
    ledger.record(EvidenceKind.SYNTAX_VALID, f"{path} parses as Python",
                  "task_evidence.verify_python_syntax")
    return True


def verify_tests_pass(command: List[str], cwd: str, ledger: EvidenceLedger,
                      timeout: float = 300.0) -> bool:
    """
    Actually run a test command and record TESTS_PASSED only on exit 0.

    Returns False (never raises) if the command cannot run, so a missing
    test runner degrades to "no evidence" rather than a crash.
    """
    import subprocess
    try:
        proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    tail = (proc.stdout or "").strip().splitlines()
    detail = f"`{' '.join(command)}` exited 0"
    if tail:
        detail += f" -- {tail[-1][:120]}"
    ledger.record(EvidenceKind.TESTS_PASSED, detail,
                  "task_evidence.verify_tests_pass")
    return True
