"""
Saleha Core: Memory Engineering Subsystem (2026 Frontier Standard)

Provides unified multi-tier memory, persistent solution cache, episodic journals,
and vector recall across projects:
- MemoryStore / memory_store (Verified long-term solution knowledge base)
- MemoryJournal / memory_journal (Timestamped decision audit trail)
- ProjectMemory / get_project_memory (Per-project persistent episodic store)
- SemanticMemoryCache / semantic_memory (Vector-indexed episodic cache)
- TriTierMemoryEngine (Working memory, episodic history, and semantic knowledge graph)
"""

from __future__ import annotations

from saleha.core.memory.memory_journal import JournalEntry, MemoryJournal, memory_journal
from saleha.core.memory.memory_store import MemoryEntry, MemoryStore, memory_store
from saleha.core.memory.project_memory import (
    DEFAULT_MEMORY_DIR,
    ProjectMemory,
    get_project_memory,
)
from saleha.core.memory.semantic_memory_cache import (
    SemanticMemoryCache,
    semantic_memory,
)
from saleha.core.memory.tri_tier_memory import (
    EpisodicMemory,
    EpisodicRecord,
    GraphTriple,
    SemanticKnowledgeGraph,
    TriTierMemoryEngine,
    WorkingMemory,
    WorkingMemoryTurn,
)

__all__ = [
    "MemoryStore",
    "MemoryEntry",
    "memory_store",
    "MemoryJournal",
    "JournalEntry",
    "memory_journal",
    "ProjectMemory",
    "get_project_memory",
    "DEFAULT_MEMORY_DIR",
    "SemanticMemoryCache",
    "semantic_memory",
    "TriTierMemoryEngine",
    "WorkingMemory",
    "WorkingMemoryTurn",
    "EpisodicMemory",
    "EpisodicRecord",
    "SemanticKnowledgeGraph",
    "GraphTriple",
]
