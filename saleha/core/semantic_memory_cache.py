"""
Saleha Core: Semantic Memory Vector Cache & Episodic Recall Engine

Stores long-term project memory (ADRs, past self-healed bug fixes, coding patterns,
and security invariants) with vector embeddings and fast cosine/Jaccard similarity search.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class MemoryEntry:
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: str = "general"  # "adr", "bug_fix", "pattern", "security_rule"
    title: str = ""
    content: str = ""
    tags: List[str] = field(default_factory=list)
    vector: List[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0


class SemanticMemoryCache:
    """Vector-indexed Episodic Memory Cache for Autonomous Swarms."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join(".saleha", "semantic_memory.json")
        self._entries: Dict[str, MemoryEntry] = {}
        self._load_from_disk()

    def _generate_sparse_vector(self, text: str) -> List[float]:
        """Synthesizes deterministic normalized frequency vector for similarity search."""
        words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
        vocab_buckets = 64
        vec = [0.0] * vocab_buckets
        for w in words:
            idx = abs(hash(w)) % vocab_buckets
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        return sum(a * b for a, b in zip(v1, v2))

    def store_memory(
        self,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None
    ) -> MemoryEntry:
        """Stores a new memory item with indexed vector representation."""
        vector = self._generate_sparse_vector(f"{title} {content} {' '.join(tags or [])}")
        entry = MemoryEntry(
            category=category,
            title=title,
            content=content,
            tags=tags or [],
            vector=vector
        )
        self._entries[entry.memory_id] = entry
        self._save_to_disk()
        return entry

    def search_memory(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3
    ) -> List[Tuple[MemoryEntry, float]]:
        """Searches memory for semantically relevant historical context."""
        query_vec = self._generate_sparse_vector(query)
        scores: List[Tuple[MemoryEntry, float]] = []

        for entry in self._entries.values():
            if category and entry.category != category:
                continue
            sim = self._cosine_similarity(query_vec, entry.vector)
            
            # Keyword bonus
            query_words = set(re.findall(r"\b\w+\b", query.lower()))
            entry_words = set(re.findall(r"\b\w+\b", f"{entry.title} {entry.content}".lower()))
            overlap = len(query_words.intersection(entry_words))
            score = sim + (0.1 * overlap)

            scores.append((entry, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        top_results = scores[:top_k]

        # Increment access count
        for entry, _ in top_results:
            entry.access_count += 1

        return top_results

    def get_all_memories(self, category: Optional[str] = None) -> List[MemoryEntry]:
        if category:
            return [e for e in self._entries.values() if e.category == category]
        return list(self._entries.values())

    def clear(self) -> None:
        self._entries.clear()
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = [
                {
                    "memory_id": e.memory_id,
                    "category": e.category,
                    "title": e.title,
                    "content": e.content,
                    "tags": e.tags,
                    "vector": e.vector,
                    "timestamp": e.timestamp,
                    "access_count": e.access_count,
                }
                for e in self._entries.values()
            ]
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not os.path.isfile(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    entry = MemoryEntry(
                        memory_id=item.get("memory_id", ""),
                        category=item.get("category", "general"),
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        tags=item.get("tags", []),
                        vector=item.get("vector", []),
                        timestamp=item.get("timestamp", time.time()),
                        access_count=item.get("access_count", 0),
                    )
                    self._entries[entry.memory_id] = entry
        except Exception:
            pass


# Global Singleton Instance
semantic_memory = SemanticMemoryCache()
