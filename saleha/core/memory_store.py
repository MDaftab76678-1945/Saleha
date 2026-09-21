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

import contextlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from saleha.core.rag.vector_store import VectorStore


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
    def __init__(self, storage_path: Optional[str] = None) -> None:
        if storage_path is None:
            home = os.path.expanduser("~")
            saleha_dir = os.path.join(home, ".saleha")
            os.makedirs(saleha_dir, exist_ok=True)
            storage_path = os.path.join(saleha_dir, "memory.json")
        self.storage_path = storage_path
        self._entries: Dict[str, MemoryEntry] = {}
        self.vector_store = VectorStore()
        self._load()

    def _sync_vector_store(self) -> None:
        """Full rebuild of the vector index from in-memory entries.
        Used only during initial load. Incremental modifications (remember/delete)
        directly mutate vector_store without re-embedding the entire collection."""
        self.vector_store.clear()
        docs = []
        for entry in self._entries.values():
            content = f"{entry.goal}\n{' '.join(entry.tags)}\n{entry.code}"
            docs.append((entry.id, content, {"goal": entry.goal, "tags": entry.tags}))
        self.vector_store.add_documents(docs)

    def _doc_text(self, entry: MemoryEntry) -> str:
        return f"{entry.goal}\n{' '.join(entry.tags)}\n{entry.code}"

    def _load(self) -> None:
        self._entries.clear()
        if not os.path.isfile(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("entries", []):
                entry = MemoryEntry(
                    id=item.get("id", uuid.uuid4().hex[:8]),
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
        except (json.JSONDecodeError, OSError):
            # Corrupted store file; resetting
            self._entries = {}

    def _save(self) -> None:
        """Atomic disk persistence -- writes to tmp file then replaces atomically."""
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
            tmp_path = f"{self.storage_path}.tmp.{os.getpid()}"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.storage_path)
            except Exception:
                if os.path.exists(tmp_path):
                    with contextlib.suppress(OSError):
                        os.remove(tmp_path)

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

    def clear(self) -> None:
        self._entries.clear()
        self.vector_store.clear()
        self._save()

    def export_json(self, target_path: str) -> bool:
        """Exports all memories to a standalone JSON file for backup or sharing."""
        try:
            target = os.path.abspath(target_path)
            dirname = os.path.dirname(target)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            data = {
                "version": "1.0.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_entries": len(self._entries),
                "entries": [asdict(e) for e in self._entries.values()],
            }
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def import_json(self, source_path: str, overwrite: bool = False) -> int:
        """Imports memories from an external JSON file, returning count of imported entries."""
        if not os.path.isfile(source_path):
            return 0
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            count = 0
            for item in data.get("entries", []):
                goal = str(item.get("goal", "")).strip()
                code = str(item.get("code", "")).strip()
                if not goal or not code:
                    continue
                if not overwrite and any(e.goal.strip().lower() == goal.lower() for e in self._entries.values()):
                    continue
                self.remember(
                    goal=goal,
                    code=code,
                    tags=item.get("tags", []),
                    model=item.get("model", "auto"),
                    source_type=item.get("source_type", "imported"),
                    metadata=item.get("metadata", {}),
                )
                count += 1
            return count
        except Exception:
            return 0

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

    def recall(self, query: str, min_similarity: float = 0.80,
               model: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Looks for a high-confidence matching verified solution.

        `model`, when given, restricts the search to entries produced by that
        model. This matters for any before/after or A/B comparison: the cache
        is keyed on goal text alone, so benchmarking model B on the same
        prompts model A already solved would replay A's cached answer and
        report B's score as A's. That was verified to happen -- it produced
        identical, meaningless before/after numbers in a real tuning run.
        Callers doing plain task execution can leave it None and keep sharing
        solutions across models, which is the useful behaviour there.
        """
        query_norm = query.strip().lower()
        if not query_norm or not self._entries:
            return None

        candidates = [
            e for e in self._entries.values()
            if model is None or e.model == model
        ]
        if not candidates:
            return None

        # 1. Exact match
        for entry in candidates:
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

        for entry in candidates:
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

    @staticmethod
    def compact_conversation_history(transcript_steps: List[Dict[str, Any]], max_chars: int = 4000) -> str:
        """
        Hierarchically compacts multi-turn agent conversation steps into a token-efficient summary.
        Keeps recent actions detailed while condensing older tool observations into semantic bullet points.
        """
        if not transcript_steps:
            return "(no history)"

        if len(transcript_steps) <= 4:
            lines = []
            for s in transcript_steps:
                lines.append(f"[Step {s.get('step', '?')}] {s.get('action')}({s.get('args', '')}) -> {s.get('observation', '')[:200]}")
            return "\n".join(lines)

        older = transcript_steps[:-4]
        recent = transcript_steps[-4:]

        compact_lines = ["### [CONTEXT] Compacted Prior Investigation Context:"]
        for s in older:
            action = s.get("action", "")
            step_no = s.get("step", "?")
            obs = str(s.get("observation", ""))
            first_line = obs.strip().splitlines()[0] if obs.strip() else "done"
            compact_lines.append(f"- Step {step_no} ({action}): {first_line[:120]}")

        compact_lines.append("\n### [TRACE] Recent Detailed Trace:")
        for s in recent:
            step_no = s.get("step", "?")
            action = s.get("action", "")
            args = str(s.get("args", ""))[:80]
            obs = str(s.get("observation", ""))[:300]
            compact_lines.append(f"[Step {step_no}] {action}({args})\nOBSERVATION: {obs}")

        full_compact = "\n".join(compact_lines)
        if len(full_compact) > max_chars:
            return full_compact[:max_chars] + "\n...(older context pruned for budget)"
        return full_compact


# Global memory store instance
memory_store = MemoryStore()


