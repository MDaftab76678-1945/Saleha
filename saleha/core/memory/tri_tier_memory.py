"""
Tri-Tier Persistent Memory System for Saleha Platform.
Tier 1: In-Memory Working Memory (Cache-aligned ring buffer)
Tier 2: Episodic Memory (Log & task history with fast indexing)
Tier 3: Semantic Knowledge Graph (.salehagraph persistent triple store)
"""

from __future__ import annotations

import collections
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WorkingMemoryTurn:
    turn_id: int
    user_prompt: str
    agent_response: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class EpisodicRecord:
    record_id: int
    agent_id: int
    task_summary: str
    status: str
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class GraphTriple:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)


class WorkingMemory:
    """Tier 1: In-Memory Fast Ring Buffer (< 1MB RAM)."""

    def __init__(self, max_turns: int = 16) -> None:
        self.max_turns = max_turns
        self.ring: collections.deque[WorkingMemoryTurn] = collections.deque(maxlen=max_turns)
        self._current_id = 0

    def append(self, prompt: str, response: str) -> WorkingMemoryTurn:
        self._current_id += 1
        turn = WorkingMemoryTurn(
            turn_id=self._current_id,
            user_prompt=prompt,
            agent_response=response,
        )
        self.ring.append(turn)
        return turn

    def get_recent_context(self, limit: int = 5) -> List[WorkingMemoryTurn]:
        return list(self.ring)[-limit:]

    def clear(self) -> None:
        self.ring.clear()


class EpisodicMemory:
    """Tier 2: Persistent Task & Error Logs on NVMe/Disk."""

    def __init__(self, storage_path: str = ".saleha/episodic_memory.jsonl") -> None:
        self.storage_path = Path(storage_path)
        self.records: List[EpisodicRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        # Real bug found auditing this module: the try/except wrapped the
        # whole loop, so one corrupted line (e.g. from a crash mid-write)
        # silently discarded every record after it, not just that line.
        # Confirmed by direct probe: a 3-line file with one bad middle line
        # loaded only the first record, losing a perfectly valid third one.
        # Each line now fails independently.
        try:
            f = open(self.storage_path, "r", encoding="utf-8")
        except OSError:
            return
        with f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    self.records.append(EpisodicRecord(**data))
                except (json.JSONDecodeError, TypeError):
                    continue

    def record(self, agent_id: int, summary: str, status: str, tags: Optional[List[str]] = None) -> EpisodicRecord:
        rec = EpisodicRecord(
            record_id=len(self.records) + 1,
            agent_id=agent_id,
            task_summary=summary,
            status=status,
            tags=tags or [],
        )
        self.records.append(rec)
        
        # Append to disk
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(rec)) + "\n")
        except Exception:
            pass

        return rec

    def search(self, keyword: str, limit: int = 5) -> List[EpisodicRecord]:
        kw = keyword.lower()
        matches = [
            r for r in self.records
            if kw in r.task_summary.lower() or any(kw in tag.lower() for tag in r.tags)
        ]
        return matches[-limit:]


class SemanticKnowledgeGraph:
    """Tier 3: Permanent Semantic Graph (.salehagraph on Disk)."""

    def __init__(self, storage_path: str = ".saleha/semantic_graph.json") -> None:
        self.storage_path = Path(storage_path)
        self.triples: List[GraphTriple] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, list):
            return
        # Same class of bug as EpisodicMemory._load above: converting every
        # element in one list comprehension meant one malformed triple (a
        # dict missing a required field) raised and lost the whole graph,
        # not just that entry. Confirmed by direct probe: 3 triples, one
        # missing "object", loaded 0 -- not the 2 valid ones. Each
        # conversion now fails independently.
        triples = []
        for t in data:
            try:
                triples.append(GraphTriple(**t))
            except TypeError:
                continue
        self.triples = triples

    def insert_fact(self, subject: str, predicate: str, obj: str, confidence: float = 1.0) -> None:
        # Avoid duplicate triples
        for t in self.triples:
            if t.subject == subject and t.predicate == predicate and t.object == obj:
                t.confidence = confidence
                return
        
        self.triples.append(
            GraphTriple(subject=subject, predicate=predicate, object=obj, confidence=confidence)
        )
        self._save()

    def query_subject(self, subject: str) -> List[GraphTriple]:
        sub_lower = subject.lower()
        return [t for t in self.triples if t.subject.lower() == sub_lower]

    def query_relations(self, keyword: str) -> List[GraphTriple]:
        kw = keyword.lower()
        return [
            t for t in self.triples
            if kw in t.subject.lower() or kw in t.predicate.lower() or kw in t.object.lower()
        ]

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Atomic write: a crash mid-write must not leave a half-written
            # graph behind (same tmp+replace pattern as task_scheduler).
            tmp_path = self.storage_path.with_name(self.storage_path.name + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump([asdict(t) for t in self.triples], f, indent=2)
            tmp_path.replace(self.storage_path)
        except Exception:
            pass


class TriTierMemoryEngine:
    """Unified Tri-Tier Memory Controller for Saleha Agents."""

    def __init__(self, base_dir: str = ".saleha") -> None:
        base_path = Path(base_dir)
        self.working = WorkingMemory(max_turns=16)
        self.episodic = EpisodicMemory(str(base_path / "episodic_memory.jsonl"))
        self.semantic = SemanticKnowledgeGraph(str(base_path / "semantic_graph.json"))

    def recall_context(self, query: str) -> Dict[str, Any]:
        """Recalls context across all 3 tiers in sub-millisecond time."""
        recent_turns = self.working.get_recent_context(limit=3)
        past_episodes = self.episodic.search(query, limit=3)
        graph_facts = self.semantic.query_relations(query)

        return {
            "working_memory": [
                {"turn": t.turn_id, "prompt": t.user_prompt, "response": t.agent_response}
                for t in recent_turns
            ],
            "episodic_history": [
                {"id": e.record_id, "summary": e.task_summary, "status": e.status}
                for e in past_episodes
            ],
            "semantic_facts": [
                f"({t.subject}) --[{t.predicate}]--> ({t.object})"
                for t in graph_facts
            ],
        }

