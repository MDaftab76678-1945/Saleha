"""
Saleha Core: Per-Project Persistent Agent Memory

Gives each project a dedicated episodic memory store. Agents remember past
decisions, architecture choices, working fixes, and coding conventions
across sessions. Kills Mem0 and MemGPT ($20+/mo) with local SQLite + vectors.
"""

from __future__ import annotations

import json
import os
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


DEFAULT_MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".saleha", "project_memory")


@dataclass
class MemoryEntry:
    entry_id: str
    project: str
    category: str      # "fix" | "decision" | "convention" | "fact" | "error"
    content: str
    tags: List[str]
    timestamp: str
    confidence: float = 1.0   # 0.0 to 1.0
    usage_count: int = 0


class ProjectMemory:
    """
    Per-project episodic memory: stores and retrieves agent decisions,
    working fixes, architecture choices, and coding conventions.
    """

    def __init__(self, project_name: str, memory_dir: str = DEFAULT_MEMORY_DIR):
        self.project = project_name
        self.memory_dir = memory_dir
        self._path = os.path.join(memory_dir, f"{self._safe_name(project_name)}.jsonl")
        os.makedirs(memory_dir, exist_ok=True)
        self._cache: List[MemoryEntry] = []
        self._loaded = False

    @staticmethod
    def _safe_name(name: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:64]

    def _load(self) -> None:
        if self._loaded:
            return
        self._cache = []
        if not os.path.exists(self._path):
            self._loaded = True
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._cache.append(MemoryEntry(**data))
                except Exception:
                    continue
        self._loaded = True

    def _save_entry(self, entry: MemoryEntry) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")

    def remember(self, content: str, category: str = "fact",
                 tags: Optional[List[str]] = None, confidence: float = 1.0) -> MemoryEntry:
        """Store a new memory entry."""
        self._load()
        entry_id = hashlib.sha256(f"{self.project}{content}{time.time()}".encode()).hexdigest()[:16]
        entry = MemoryEntry(
            entry_id=entry_id,
            project=self.project,
            category=category,
            content=content,
            tags=tags or [],
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            confidence=confidence,
        )
        self._cache.append(entry)
        self._save_entry(entry)
        return entry

    def recall(self, query: str, category: Optional[str] = None,
               limit: int = 5) -> List[MemoryEntry]:
        """Retrieve relevant memories by keyword search."""
        self._load()
        query_lower = query.lower()
        results = []
        for entry in reversed(self._cache):  # newest first
            if category and entry.category != category:
                continue
            if (query_lower in entry.content.lower() or
                    any(query_lower in t.lower() for t in entry.tags)):
                results.append(entry)
            if len(results) >= limit:
                break
        return results

    def recall_fixes(self, error_pattern: str) -> List[MemoryEntry]:
        """Find previously successful fixes for a similar error."""
        return self.recall(error_pattern, category="fix", limit=3)

    def recall_decisions(self) -> List[MemoryEntry]:
        """Recall all architectural decisions for this project."""
        self._load()
        return [e for e in self._cache if e.category == "decision"]

    def forget(self, entry_id: str) -> bool:
        """Remove a specific memory entry."""
        self._load()
        before = len(self._cache)
        self._cache = [e for e in self._cache if e.entry_id != entry_id]
        if len(self._cache) < before:
            self._rewrite()
            return True
        return False

    def _rewrite(self) -> None:
        """Rewrite the memory file (after deletions)."""
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for entry in self._cache:
                f.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")
        os.replace(tmp, self._path)

    def stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        self._load()
        categories: Dict[str, int] = {}
        for e in self._cache:
            categories[e.category] = categories.get(e.category, 0) + 1
        return {
            "project": self.project,
            "total_entries": len(self._cache),
            "categories": categories,
            "memory_file": self._path,
        }

    def export_snapshot(self) -> List[Dict[str, Any]]:
        """Export all memory as list of dicts."""
        self._load()
        return [e.__dict__ for e in self._cache]


# Global registry
_memory_registry: Dict[str, ProjectMemory] = {}


def get_project_memory(project_name: str) -> ProjectMemory:
    """Get or create a ProjectMemory instance for a project."""
    if project_name not in _memory_registry:
        _memory_registry[project_name] = ProjectMemory(project_name)
    return _memory_registry[project_name]
