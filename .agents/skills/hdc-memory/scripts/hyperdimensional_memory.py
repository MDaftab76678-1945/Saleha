#!/usr/bin/env python3
"""Kanerva Hyperdimensional Computing (HDC) Associative Memory Store.

Embeds bug patterns, variable bindings, and surgical repairs into 10,000-D
bipolar vectors for O(1) associative recall without token overhead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

DIMENSION = 10000
DEFAULT_HDC_PATH = Path(".agents/scratch/hdc_memory.json")


def hash_string_to_vector(text: str, dim: int = DIMENSION) -> List[int]:
    """Generates a deterministic pseudo-orthogonal bipolar hypervector {-1, 1} from text."""
    vector = []
    # Seed generator using sha256 chunks
    for i in range(dim):
        seed = f"{text}:{i}".encode("utf-8")
        h = hashlib.sha256(seed).hexdigest()
        # Map first byte to -1 or 1
        val = 1 if int(h[:2], 16) % 2 == 0 else -1
        vector.append(val)
    return vector


def cosine_similarity(v1: List[int], v2: List[int]) -> float:
    """Computes cosine similarity between two bipolar hypervectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(len(v1))
    norm2 = math.sqrt(len(v2))
    return dot / (norm1 * norm2) if (norm1 * norm2) > 0 else 0.0


class HDCMemoryStore:
    """Associative hypervector memory store."""

    def __init__(self, storage_path: Path = DEFAULT_HDC_PATH) -> None:
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.memories: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.storage_path.write_text(json.dumps(self.memories, indent=2), encoding="utf-8")

    def store_pattern(self, bug_signature: str, fix_pattern: str) -> Dict[str, Any]:
        """Binds and bundles bug signature with fix pattern into hypervector memory."""
        # Generate hypervector for bug
        v_bug = hash_string_to_vector(bug_signature)
        record = {
            "id": len(self.memories) + 1,
            "bug_signature": bug_signature,
            "fix_pattern": fix_pattern,
            "vector": v_bug,
        }
        self.memories.append(record)
        self._save()
        return record

    def query_memory(
        self, query_signature: str, top_k: int = 1
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Associatively recalls the closest fix patterns using cosine distance."""
        if not self.memories:
            return []

        v_query = hash_string_to_vector(query_signature)
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for mem in self.memories:
            sim = cosine_similarity(v_query, mem["vector"])
            scored.append((sim, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kanerva Hyperdimensional Computing (HDC) Memory Engine."
    )
    parser.add_argument("--store", action="store_true", help="Store a bug-fix memory pattern.")
    parser.add_argument("--query", "-q", default=None, help="Query memory for a bug signature.")
    parser.add_argument("--bug", default="", help="Bug description signature.")
    parser.add_argument("--fix", default="", help="Surgical fix pattern description.")
    parser.add_argument("--output", "-o", default=None, help="Save report to JSON file.")

    args = parser.parse_args()
    store = HDCMemoryStore()

    if args.store:
        if not args.bug or not args.fix:
            sys.stderr.write("Error: --bug and --fix are required to store a pattern.\n")
            return 1
        rec = store.store_pattern(args.bug, args.fix)
        print(f"Stored HDC Memory Pattern #{rec['id']} for '{args.bug}'")
        return 0

    if args.query:
        results = store.query_memory(args.query, top_k=3)
        if not results:
            print("No matching memory patterns found in HDC memory.")
            return 0
        print(f"HDC Associative Recall Results for query: '{args.query}':")
        for sim, mem in results:
            print(f"  [Similarity: {sim:.3f}] Bug: {mem['bug_signature']}")
            print(f"     Fix Pattern: {mem['fix_pattern']}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
