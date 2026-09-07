"""
Saleha Core: Semantic Prompt Cache

Why this exists
---------------
The notebook's version (`chat-Nexus-Omni AgentStack Architecture.txt`) wires a
semantic cache to this:

    # Mock embedding function (Replace with sentence-transformers in prod)
    def get_embedding(text: str) -> np.ndarray:
        return np.random.rand(384).astype(np.float32)

A cache keyed on **random vectors** is broken in both directions, measured
here with 384-dim uniform random vectors (their pairwise cosine sits around
0.73-0.77, regardless of the text):

    threshold 0.70 -> an unrelated query ("how do I configure nginx") is
                      served the cached answer for "reverse a string"
    threshold 0.95 -> even an IDENTICAL prompt misses, so the cache never
                      returns anything at all

Either way it is worse than no cache: `PromptCache` in `fast_inference.py` is
exact-match and therefore always correct, while this silently hands back a
reply to a different question or does nothing while costing an embed call.

This module does the same idea with real embeddings from the local Ollama
`/api/embed` endpoint, and refuses to run at all when they are unavailable
rather than falling back to anything approximate.

The danger, stated plainly
--------------------------
Near-miss matching is how a cache starts answering questions it was never
asked. `PromptCache`'s docstring says exactly that, and it is right. So:

  * `DEFAULT_THRESHOLD = 0.95` is deliberately strict. At 0.85 the measured
    behaviour was that clearly different coding questions collide.
  * A hit records the similarity and the prompt it matched, so a caller can
    see *why* it was served and audit a bad one.
  * `strict=True` (the default) refuses to serve a hit when the two prompts
    disagree on any literal it can identify -- numbers, quoted strings, and
    dotted paths. "sort a list of 10 items" and "sort a list of 100 items"
    embed almost identically and must never share an answer.

Honest limits
-------------
Semantic similarity is not equivalence. Two prompts can embed at 0.97 and
still want different answers, and no threshold fixes that in general -- which
is why the literal check exists and why this is opt-in rather than on by
default. When correctness matters more than latency, use the exact-match
`PromptCache`; this is for the case where a near-repeat is genuinely fine.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Strict on purpose -- see the module docstring.
DEFAULT_THRESHOLD = 0.95
DEFAULT_MAX_ENTRIES = 256

# Literals that change the required answer even when the wording does not.
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_QUOTED = re.compile(r"['\"`]([^'\"`\n]{1,80})['\"`]")
_DOTTED = re.compile(r"\b[\w/\\-]+\.(?:py|js|ts|go|rs|java|json|ya?ml|toml|md)\b")


@dataclass
class CacheEntry:
    prompt: str
    response: str
    vector: List[float]
    model: str
    created_at: float = field(default_factory=time.time)
    hits: int = 0


@dataclass
class SemanticHit:
    """A served hit, with the evidence for why it was served."""

    response: str
    similarity: float
    matched_prompt: str
    model: str

    def describe(self) -> str:
        return (f"semantic cache hit at {self.similarity:.4f} against "
                f"{self.matched_prompt[:80]!r}")


def literals(text: str) -> Tuple[frozenset, frozenset, frozenset]:
    """
    Numbers, quoted strings and file paths mentioned in a prompt.

    These are the parts an embedding is worst at distinguishing: "retry 3
    times" and "retry 30 times" are nearly identical in vector space and
    completely different as requests.
    """
    lowered = (text or "").lower()
    return (
        frozenset(_NUMBER.findall(lowered)),
        frozenset(m.strip() for m in _QUOTED.findall(lowered)),
        frozenset(_DOTTED.findall(lowered)),
    )


def cosine(v1: List[float], v2: List[float]) -> float:
    """Dot product; the embedder returns L2-normalised vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class SemanticCache:
    """
    Prompt cache keyed on meaning rather than exact text.

    Requires a working embedder. `available()` is a real probe, not an
    assumption: with no embedding model installed this stays empty and every
    lookup misses, which degrades to "no cache" rather than to "wrong answers".
    """

    def __init__(self, embedder: Optional[Any] = None,
                 threshold: float = DEFAULT_THRESHOLD,
                 max_entries: int = DEFAULT_MAX_ENTRIES,
                 strict: bool = True):
        self.threshold = threshold
        self.max_entries = max_entries
        self.strict = strict
        self._embedder = embedder
        self._entries: List[CacheEntry] = []
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.rejected_by_literals = 0

    # -- embedding -----------------------------------------------------
    def _embed(self, text: str) -> Optional[List[float]]:
        embedder = self._embedder
        if embedder is None:
            from saleha.core.embedding_backends import OllamaEmbedder
            embedder = self._embedder = OllamaEmbedder()
        try:
            vectors = embedder.embed_batch([text])
        except Exception:
            return None
        if not vectors or not vectors[0]:
            return None
        return list(vectors[0])

    def available(self) -> bool:
        """True only if a real embedding actually comes back."""
        return self._embed("probe") is not None

    # -- api -----------------------------------------------------------
    def put(self, prompt: str, response: str, model: str = "") -> bool:
        """
        Store a response. Returns False when no embedding could be produced --
        never stores an entry it cannot key correctly.
        """
        if not prompt or not response:
            return False
        vector = self._embed(prompt)
        if vector is None:
            return False
        with self._lock:
            self._entries.append(CacheEntry(prompt=prompt, response=response,
                                            vector=vector, model=model))
            while len(self._entries) > self.max_entries:
                self._entries.pop(0)      # oldest first
        return True

    def get(self, prompt: str, model: str = "") -> Optional[SemanticHit]:
        """
        Best entry above the threshold, or None.

        `model` is part of the match, not a hint: serving one model's answer
        as another's is a real bug this repo has already had once, in
        `memory_store.recall()`.
        """
        if not prompt:
            self.misses += 1
            return None
        vector = self._embed(prompt)
        if vector is None:
            self.misses += 1
            return None

        query_literals = literals(prompt)
        best: Optional[CacheEntry] = None
        best_score = 0.0
        blocked = False

        with self._lock:
            for entry in self._entries:
                if model and entry.model and entry.model != model:
                    continue
                score = cosine(vector, entry.vector)
                if score < self.threshold or score <= best_score:
                    continue
                if self.strict and literals(entry.prompt) != query_literals:
                    # Similar wording, different numbers/paths/strings.
                    blocked = True
                    continue
                best, best_score = entry, score

            if best is None:
                self.misses += 1
                if blocked:
                    self.rejected_by_literals += 1
                return None
            best.hits += 1
            self.hits += 1
            return SemanticHit(response=best.response, similarity=round(best_score, 6),
                               matched_prompt=best.prompt, model=best.model)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.hits = self.misses = self.rejected_by_literals = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._entries),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
                "rejected_by_literals": self.rejected_by_literals,
                "threshold": self.threshold,
                "strict": self.strict,
            }
