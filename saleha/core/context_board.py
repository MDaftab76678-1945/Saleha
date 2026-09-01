"""
Saleha Core: Swarm Shared Context Blackboard (ContextBoard)

Provides a centralized, thread-safe asynchronous blackboard for multi-agent swarms:
1. Shared state, hypotheses, verified facts, and threat alerts across agents.
2. Pub/Sub subscription events for real-time agent coordination.
3. Telemetry and exportable Markdown/JSON boards for live terminal dashboards.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable


@dataclass
class BoardEntry:
    """Represents a single piece of shared state on the blackboard."""
    entry_id: str
    entry_type: str  # "hypothesis", "fact", "threat", "artifact", "metric"
    agent_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    verified: bool = False


class ContextBoard:
    """Thread-safe multi-agent blackboard for swarm state coordination and consensus."""

    def __init__(self, board_name: str = "default_swarm_board"):
        """Initializes the Swarm Context Blackboard."""
        self.board_name = board_name
        self._entries: List[BoardEntry] = []
        self._subscribers: Dict[str, List[Callable[[BoardEntry], None]]] = {}
        self._lock = threading.Lock()

    def post(
        self,
        entry_type: str,
        agent_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        verified: bool = False,
    ) -> BoardEntry:
        """Posts a new entry onto the blackboard and notifies relevant subscribers."""
        with self._lock:
            entry_id = f"entry_{len(self._entries) + 1}_{int(time.time() * 1000) % 10000}"
            entry = BoardEntry(
                entry_id=entry_id,
                entry_type=entry_type,
                agent_id=agent_id,
                content=content,
                metadata=metadata or {},
                verified=verified,
            )
            self._entries.append(entry)

        # Notify subscribers
        self._notify_subscribers(entry)
        return entry

    def post_hypothesis(self, agent_id: str, hypothesis: str, metadata: Optional[Dict[str, Any]] = None) -> BoardEntry:
        """Helper to post a working hypothesis."""
        return self.post("hypothesis", agent_id, hypothesis, metadata)

    def post_fact(self, agent_id: str, fact: str, metadata: Optional[Dict[str, Any]] = None) -> BoardEntry:
        """Helper to post a verified ground truth."""
        return self.post("fact", agent_id, fact, metadata, verified=True)

    def post_threat(self, agent_id: str, threat: str, severity: str = "HIGH") -> BoardEntry:
        """Helper to post a security threat alert."""
        return self.post("threat", agent_id, threat, metadata={"severity": severity})

    def post_artifact(self, agent_id: str, artifact_name: str, code: str) -> BoardEntry:
        """Helper to post a shared code or design artifact."""
        return self.post("artifact", agent_id, artifact_name, metadata={"code": code}, verified=True)

    def get_entries(self, entry_type: Optional[str] = None, agent_id: Optional[str] = None) -> List[BoardEntry]:
        """Retrieves entries matching optional filters."""
        with self._lock:
            results = self._entries
            if entry_type:
                results = [e for e in results if e.entry_type == entry_type]
            if agent_id:
                results = [e for e in results if e.agent_id == agent_id]
            return list(results)

    def subscribe(self, entry_type: str, callback: Callable[[BoardEntry], None]):
        """Subscribes a callback to receive events for a specific entry type or '*' for all."""
        with self._lock:
            if entry_type not in self._subscribers:
                self._subscribers[entry_type] = []
            self._subscribers[entry_type].append(callback)

    def _notify_subscribers(self, entry: BoardEntry):
        """Notifies registered listeners of a new blackboard post."""
        listeners = []
        with self._lock:
            listeners.extend(self._subscribers.get(entry.entry_type, []))
            listeners.extend(self._subscribers.get("*", []))

        for cb in listeners:
            try:
                cb(entry)
            except Exception:
                pass  # noqa

    def clear(self):
        """Clears all entries from the blackboard."""
        with self._lock:
            self._entries.clear()

    def export_markdown(self) -> str:
        """Renders the blackboard as a Markdown document."""
        with self._lock:
            lines = [
                f"# Swarm Context Board: {self.board_name}",
                f"**Total Entries**: {len(self._entries)}\n",
                "| ID | Type | Agent | Content | Verified |",
                "| :--- | :---: | :--- | :--- | :---: |",
            ]
            for e in self._entries:
                v_icon = "✅" if e.verified else "⏳"
                lines.append(f"| `{e.entry_id}` | `{e.entry_type}` | `{e.agent_id}` | {e.content[:60]} | {v_icon} |")
            return "\n".join(lines)


# Global singleton instance for shared swarm coordination
global_context_board = ContextBoard()


if __name__ == "__main__":
    _board = ContextBoard()
    _board.post_hypothesis("Architect", "Database layer should use connection pooling")
    _board.post_fact("Tester", "Connection pooling passed 10,000 concurrency requests")
    _board.post_threat("SecurityEngineer", "Unauthenticated endpoint /debug exposed", "CRITICAL")
