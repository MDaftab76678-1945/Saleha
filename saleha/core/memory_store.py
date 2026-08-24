"""
Saleha Core: Memory Store (Long-Term Solution & Knowledge Base)

Persists verified solutions, architectural patterns, and execution context
across sessions in `~/.saleha/memory.json`.

Features:
1. Fast semantic/token-overlap recall: checks if a similar goal was solved and verified before.
2. Tag-based indexing and search.
3. Automatic caching upon successful test verification.
4. Hit counter tracking to identify frequently reused patterns.
"""

import os
import json
import uuid
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple

from saleha.core.vector_store import VectorStore


@dataclass
class MemoryEntry:
    id: str
    goal: str
    code: str
    tags: List[str] = field(default_factory=list)
    model: str = "auto"
    timestamp: str = ""
    hit_count: int = 0
    source_type: str = "verified_execution"  # e.g., 'verified_execution', 'swarm_deliverable', 'manual'
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryStore:
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            home = os.path.expanduser("~")
            saleha_dir = os.path.join(home, ".saleha")
            os.makedirs(saleha_dir, exist_ok=True)
            storage_path = os.path.join(saleha_dir, "memory.json")
        self.storage_path = storage_path
        self._entries: Dict[str, MemoryEntry] = {}
        self.vector_store = VectorStore()
        self._load()

    def _sync_vector_store(self):
        """FULL rebuild -- sirf initial load par use hota hai. Incremental
        updates (remember/delete) ab directly vector_store ko mutate karte
        hain; pehle har _save() par poora store re-embed hota tha (O(N^2))."""
        self.vector_store.clear()
        docs = []
        for entry in self._entries.values():
            content = f"{entry.goal}\n{' '.join(entry.tags)}\n{entry.code}"
            docs.append((entry.id, content, {"goal": entry.goal, "tags": entry.tags}))
        self.vector_store.add_documents(docs)

    def _doc_text(self, entry: MemoryEntry) -> str:
        return f"{entry.goal}\n{' '.join(entry.tags)}\n{entry.code}"

    def _load(self):
        self._entries.clear()
        if not os.path.isfile(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("entries", []):
                entry = MemoryEntry(
                    id=item.get("id", str(uuid.uuid4().hex[:8])),
                    goal=item.get("goal", ""),
                    code=item.get("code", ""),
                    tags=item.get("tags", []),
                    model=item.get("model", "auto"),
                    timestamp=item.get("timestamp", ""),
                    hit_count=item.get("hit_count", 0),
                    source_type=item.get("source_type", "verified_execution"),
                    metadata=item.get("metadata", {}),
                )
                self._entries[entry.id] = entry
            self._sync_vector_store()
        except (json.JSONDecodeError, OSError) as e:
            # Corrupted store file; resetting
            self._entries = {}

    def _save(self):
        """Sirf disk persistence -- vector store ko touch NahI karta.
        (Pehle yahin se har save par full vector resync trigger hota tha.)"""
        if self.storage_path and self.storage_path != ":memory:":
            dirname = os.path.dirname(self.storage_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            data = {
                "version": "1.0.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "total_entries": len(self._entries),
                "entries": [asdict(e) for e in self._entries.values()],
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def semantic_search(self, query: str, top_k: int = 5, min_score: float = 0.05) -> List[Tuple[MemoryEntry, float]]:
        """Performs TF-IDF Cosine Similarity semantic search over memory store."""
        vec_results = self.vector_store.search(query, top_k=top_k, min_score=min_score)
        results = []
        for r in vec_results:
            entry = self._entries.get(r.doc_id)
            if entry:
                results.append((entry, round(r.score, 4)))
        return results

    def search(self, query: str) -> List[MemoryEntry]:
        """Filters memories by keyword, tag, or partial text match."""
        query_lower = query.strip().lower()
        results = []
        for entry in self._entries.values():
            if (query_lower in entry.goal.lower() or
                query_lower in entry.code.lower() or
                any(query_lower in tag.lower() for tag in entry.tags)):
                results.append(entry)
        return sorted(results, key=lambda e: -e.hit_count)

    def list_all(self, limit: int = 50) -> List[MemoryEntry]:
        entries = list(self._entries.values())
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            self.vector_store.remove_document(entry_id)  # incremental
            self._save()
            return True
        return False

    def clear(self):
        self._entries.clear()
        self.vector_store.clear()
        self._save()

    def remember(self, goal: str, code: str, tags: Optional[List[str]] = None,
                 model: str = "auto", source_type: str = "verified_execution",
                 metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        """Stores a new verified solution or updates an existing exact match."""
        if not goal.strip() or not code.strip():
            raise ValueError("Goal and code cannot be empty.")

        auto_tags = self._extract_tags(goal)
        all_tags = list(set(auto_tags + (tags or [])))

        # Check for duplicate exact goal
        for existing in self._entries.values():
            if existing.goal.strip().lower() == goal.strip().lower():
                existing.code = code
                existing.tags = list(set(existing.tags + all_tags))
                existing.model = model
                existing.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                # Incremental vector update (same doc_id overwrite)
                self.vector_store.add_document(
                    existing.id, self._doc_text(existing),
                    {"goal": existing.goal, "tags": existing.tags}
                )
                self._save()
                return existing

        entry_id = f"mem_{uuid.uuid4().hex[:8]}"
        entry = MemoryEntry(
            id=entry_id,
            goal=goal.strip(),
            code=code.strip(),
            tags=all_tags,
            model=model,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            hit_count=0,
            source_type=source_type,
            metadata=metadata or {},
        )
        self._entries[entry.id] = entry
        self.vector_store.add_document(entry.id, self._doc_text(entry), {"goal": entry.goal, "tags": entry.tags})
        self._save()
        return entry

    def recall(self, query: str, min_similarity: float = 0.80) -> Optional[MemoryEntry]:
        """Looks for a high-confidence matching verified solution."""
        query_norm = query.strip().lower()
        if not query_norm or not self._entries:
            return None

        # 1. Exact match
        for entry in self._entries.values():
            if entry.goal.strip().lower() == query_norm:
                entry.hit_count += 1
                self._save()
                return entry

        # 2. Token overlap / Jaccard similarity
        query_tokens = set(self._tokenize(query_norm))
        if not query_tokens:
            return None

        best_score = 0.0
        best_entry: Optional[MemoryEntry] = None

        for entry in self._entries.values():
            entry_tokens = set(self._tokenize(entry.goal.lower()))
            if not entry_tokens:
                continue

            intersection = query_tokens.intersection(entry_tokens)
            union = query_tokens.union(entry_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard > best_score:
                best_score = jaccard
                best_entry = entry

        if best_score >= min_similarity and best_entry:
            best_entry.hit_count += 1
            self._save()
            return best_entry

        return None

    def stats(self) -> Dict[str, Any]:
        total_hits = sum(e.hit_count for e in self._entries.values())
        return {
            "total_memories": len(self._entries),
            "total_hits": total_hits,
            "storage_path": self.storage_path,
        }

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z0-9_\u0900-\u097F]+", text.lower())
        stopwords = {"a", "an", "the", "in", "on", "of", "to", "for", "with", "and", "is", "ek", "ko", "jo", "par", "se", "ka", "ki", "ke"}
        return [w for w in words if w not in stopwords and len(w) > 1]

    def _extract_tags(self, text: str) -> List[str]:
        tokens = self._tokenize(text)
        tech_keywords = {
            "python", "rest", "api", "async", "redis", "lock", "cache", "sorting",
            "search", "kafka", "spark", "sql", "db", "auth", "jwt", "token", "http",
            "decorator", "generator", "class", "function", "graph", "tree", "matrix"
        }
        return [t for t in tokens if t in tech_keywords]


# Global memory store instance
memory_store = MemoryStore()

