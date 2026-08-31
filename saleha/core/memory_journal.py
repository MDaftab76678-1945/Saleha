"""
Saleha Core: Agent Decision Journal

Timestamped log of every agent decision, hypothesis, and action taken during
autonomous engineering sessions. Enables full auditability, replay, and
learning from past sessions across projects.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


DEFAULT_JOURNAL_DIR = os.path.join(os.path.expanduser("~"), ".saleha", "journals")


@dataclass
class JournalEntry:
    session_id: str
    project: str
    agent: str
    action: str         # "plan" | "code" | "test" | "fix" | "deploy" | "review"
    input_summary: str
    output_summary: str
    success: bool
    duration_ms: int
    timestamp: str
    model_used: str = ""
    metadata: Optional[Dict[str, Any]] = None


class MemoryJournal:
    """Append-only timestamped journal of agent decisions and actions."""

    def __init__(self, project: str, session_id: Optional[str] = None,
                 journal_dir: str = DEFAULT_JOURNAL_DIR):
        self.project = project
        self.session_id = session_id or f"session_{int(time.time())}"
        self.journal_dir = journal_dir
        os.makedirs(journal_dir, exist_ok=True)
        self._path = os.path.join(journal_dir, f"{project[:32]}.journal.jsonl")
        self._session_start = time.time()

    def log(self, agent: str, action: str, input_summary: str,
            output_summary: str, success: bool, duration_ms: int = 0,
            model_used: str = "", metadata: Optional[Dict[str, Any]] = None) -> JournalEntry:
        """Append a new decision entry to the journal."""
        entry = JournalEntry(
            session_id=self.session_id,
            project=self.project,
            agent=agent,
            action=action,
            input_summary=input_summary[:300],
            output_summary=output_summary[:300],
            success=success,
            duration_ms=duration_ms,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            model_used=model_used,
            metadata=metadata,
        )
        with open(self._path, "a", encoding="utf-8") as f:
            d = entry.__dict__.copy()
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        return entry

    def read_session(self, session_id: Optional[str] = None) -> List[JournalEntry]:
        """Read all entries for a session (default: current session)."""
        sid = session_id or self.session_id
        entries = []
        if not os.path.exists(self._path):
            return entries
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("session_id") == sid:
                        meta = data.pop("metadata", None)
                        entry = JournalEntry(**data, metadata=meta)
                        entries.append(entry)
                except Exception:
                    continue
        return entries

    def success_rate(self) -> float:
        """Compute success rate across all journal entries."""
        if not os.path.exists(self._path):
            return 0.0
        total = success = 0
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    total += 1
                    if data.get("success"):
                        success += 1
                except Exception:
                    continue
        return round(success / total, 3) if total > 0 else 0.0

    def replay_summary(self) -> str:
        """Human-readable replay of the current session."""
        entries = self.read_session()
        if not entries:
            return "No entries in current session."
        lines = [f"Session: {self.session_id} | Project: {self.project}"]
        for e in entries:
            status = "✅" if e.success else "❌"
            lines.append(f"  {status} [{e.timestamp}] {e.agent}:{e.action} ({e.duration_ms}ms)")
            lines.append(f"     IN:  {e.input_summary[:80]}")
            lines.append(f"     OUT: {e.output_summary[:80]}")
        return "\n".join(lines)


# Global instance
memory_journal = MemoryJournal(project="default")
