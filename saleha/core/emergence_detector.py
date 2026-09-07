"""
Saleha Core: Emergent Swarm Behavior & Collusion Detector (EmergenceDetector)

Monitors multi-agent handoff graphs to detect:
1. Gini Inequality: unbalanced message volume across agents.
2. Circular Deadlocks: ping-pong loops (Agent A -> Agent B -> Agent A).
3. Auto-remediation hints when either fires.

## The wiring gap this module used to have

The detection logic below was always real -- the Gini coefficient is the
standard formula and the ping-pong check does look at the recorded graph. But
nothing in the repo ever called `record_message()`, so the module-level
singleton was permanently empty, and `saleha emergence-check` printed

    "Swarm communication is idle and healthy."

on every run, on every machine, no matter what the agents had just done. It was
reporting the health of an empty list. `ARCHITECTURE.md` flagged this on
2026-09-06 as "template in this wiring"; it stayed that way until 2026-09-07.

Two things were missing, and both are fixed:

**Nobody recorded.** `TeamOrchestrator.run_team_workflow` runs a real handoff
chain (PM -> Designer -> Coder -> Security -> QA) plus a Debugger/Executor
self-healing loop, which is exactly the graph this detector describes. Those
handoffs are now recorded as they happen.

**Nothing persisted.** Even with recording, `emergence-check` runs in a
separate process from the workflow it is asking about, so an in-memory
singleton would still be empty at the moment the question is asked. Events are
now appended to `~/.saleha/swarm_messages.jsonl` and the CLI reads that.

An empty history no longer claims health. It reports that there is nothing to
judge, which is a different statement -- see `EmergenceHealthReport.has_data`.
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_HISTORY_PATH = os.path.join(
    os.path.expanduser("~"), ".saleha", "swarm_messages.jsonl"
)

# Cap on how many events a single evaluation reads back. A long-running
# project can append a lot; the health question is about recent dynamics.
MAX_REPLAY_EVENTS = 2000


@dataclass
class SwarmMessageEvent:
    """Represents a message sent between swarm agents."""
    sender_id: str
    recipient_id: str
    message_content: str
    step_index: int
    # Groups events from one workflow run, so a report can say whether a
    # deadlock happened in this run or is left over from an old one.
    run_id: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "sender": self.sender_id,
            "recipient": self.recipient_id,
            # Only a short excerpt is persisted: the graph shape is what gets
            # analysed, and full agent output would put generated code and
            # prompts on disk for no analytical gain.
            "content": (self.message_content or "")[:200],
            "step": self.step_index,
            "run_id": self.run_id,
        })

    @classmethod
    def from_dict(cls, d: dict) -> "SwarmMessageEvent":
        return cls(
            sender_id=str(d.get("sender", "")),
            recipient_id=str(d.get("recipient", "")),
            message_content=str(d.get("content", "")),
            step_index=int(d.get("step", 0) or 0),
            run_id=str(d.get("run_id", "")),
        )


@dataclass
class EmergenceHealthReport:
    """Consolidated health and safety evaluation of swarm communication dynamics."""
    is_healthy: bool
    total_messages: int
    gini_coefficient: float
    circular_deadlocks_detected: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    remediation_action: str = "none"
    summary: str = ""
    # False when there were no recorded messages at all. `is_healthy` is then
    # meaningless -- an empty graph has no dynamics to be healthy or unhealthy
    # about, and reporting it as healthy is what made this command useless.
    has_data: bool = True
    agent_count: int = 0
    run_count: int = 0


class EmergenceDetector:
    """Monitors emergent properties and prevents rogue collusion in agent swarms."""

    def __init__(self, gini_threshold: float = 0.75, max_cycle_len: int = 4,
                 history_path: Optional[str] = None, persist: bool = False):
        """
        `persist=True` appends every recorded message to `history_path` (default
        `~/.saleha/swarm_messages.jsonl`) so a later process can evaluate it.
        The CLI asks about a workflow that ran in a *different* process, so
        without this the singleton is always empty at the moment of the
        question -- which is precisely the bug this module had.
        """
        self.gini_threshold = gini_threshold
        self.max_cycle_len = max_cycle_len
        self.message_history: List[SwarmMessageEvent] = []
        self.history_path = history_path or DEFAULT_HISTORY_PATH
        self.persist = persist
        self._lock = threading.Lock()

    def record_message(self, sender: str, recipient: str, content: str,
                       step: int, run_id: str = ""):
        """Records an agent-to-agent interaction."""
        event = SwarmMessageEvent(sender, recipient, content, step, run_id)
        with self._lock:
            self.message_history.append(event)
            if self.persist:
                self._append(event)

    def _append(self, event: SwarmMessageEvent) -> None:
        """
        Append one event to the JSONL history.

        Recording is observability, never the job: a failure to write must not
        break the workflow being observed, so this swallows I/O errors rather
        than propagating them into an agent pipeline.
        """
        try:
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            with open(self.history_path, "a", encoding="utf-8") as fh:
                fh.write(event.to_json() + "\n")
        except OSError:
            pass

    def load_history(self, limit: int = MAX_REPLAY_EVENTS) -> int:
        """
        Replace in-memory history with the last `limit` persisted events.

        Returns how many were loaded. A missing or unreadable file loads
        nothing and returns 0 -- the caller then reports "no data", which is
        honest, instead of "healthy", which is not.
        """
        try:
            with open(self.history_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except (OSError, ValueError):
            return 0

        events: List[SwarmMessageEvent] = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(SwarmMessageEvent.from_dict(json.loads(line)))
            except (ValueError, TypeError, AttributeError):
                # A truncated final line (killed mid-write) must not sink the
                # whole history.
                continue
        with self._lock:
            self.message_history = events
        return len(events)

    def calculate_gini(self, counts: List[int]) -> float:
        """Calculates Gini coefficient across agent activity counts (0.0=equal, 1.0=monopoly)."""
        if not counts or sum(counts) == 0:
            return 0.0
        sorted_counts = sorted(counts)
        n = len(sorted_counts)
        numer = sum((i + 1) * val for i, val in enumerate(sorted_counts))
        denom = n * sum(sorted_counts)
        gini = (2.0 * numer) / denom - (n + 1.0) / n
        return max(0.0, min(1.0, round(gini, 3)))

    def evaluate_swarm_health(self) -> EmergenceHealthReport:
        """Audits the recorded message graph for deadlocks, runaway token usage, and Gini skew."""
        if not self.message_history:
            # Previously this returned is_healthy=True with "Swarm
            # communication is idle and healthy." Nothing had been recorded,
            # so that was a verdict about an empty list, not about the swarm.
            return EmergenceHealthReport(
                is_healthy=False,
                has_data=False,
                total_messages=0,
                gini_coefficient=0.0,
                remediation_action="none",
                summary=(
                    "No swarm activity recorded, so there is nothing to judge. "
                    "Run a multi-agent workflow (`saleha team \"<goal>\"`) "
                    "first; handoffs are recorded as they happen."
                ),
            )

        agent_activity: Dict[str, int] = defaultdict(int)
        for msg in self.message_history:
            agent_activity[msg.sender_id] += 1

        gini = self.calculate_gini(list(agent_activity.values()))

        # Check for circular ping-pong loops in recent history
        deadlocks: List[str] = []
        recent = self.message_history[-10:]
        for i in range(len(recent) - 2):
            m1 = recent[i]
            m2 = recent[i + 1]
            m3 = recent[i + 2]
            if (m1.sender_id == m2.recipient_id == m3.sender_id) and (m1.recipient_id == m2.sender_id == m3.recipient_id):
                deadlocks.append(f"Ping-Pong Deadlock between '{m1.sender_id}' and '{m1.recipient_id}'")

        anomalies: List[str] = []
        if gini > self.gini_threshold:
            anomalies.append(f"High communication inequality (Gini: {gini} > {self.gini_threshold})")
        if deadlocks:
            anomalies.extend(deadlocks)

        is_healthy = len(anomalies) == 0
        remediation = "break_deadlock_and_yield_to_orchestrator" if not is_healthy else "none"

        runs = {m.run_id for m in self.message_history if m.run_id}
        summary = (
            f"Swarm Dynamics ({len(self.message_history)} messages across "
            f"{len(agent_activity)} agents"
            + (f", {len(runs)} run(s)" if runs else "") + "): "
            f"Gini={gini}, Deadlocks={len(deadlocks)} -> "
            f"{'HEALTHY' if is_healthy else 'ANOMALY DETECTED'}"
        )

        return EmergenceHealthReport(
            is_healthy=is_healthy,
            has_data=True,
            total_messages=len(self.message_history),
            gini_coefficient=gini,
            circular_deadlocks_detected=deadlocks,
            anomalies=anomalies,
            remediation_action=remediation,
            summary=summary,
            agent_count=len(agent_activity),
            run_count=len(runs),
        )

    def clear(self, wipe_persisted: bool = False):
        """
        Clear in-memory history. With `wipe_persisted`, also truncate the
        JSONL file -- kept opt-in so an ordinary reset cannot silently destroy
        the recorded history the CLI reads.
        """
        with self._lock:
            self.message_history.clear()
        if wipe_persisted:
            try:
                os.remove(self.history_path)
            except OSError:
                pass


# The shared recorder used by orchestrators. Persistence is on: the process
# that records is not the process that later asks.
emergence_detector = EmergenceDetector(persist=True)
