"""
Saleha Core: Embedding Backends (B1 -- Local Semantic Upgrade)

Pehle vector store sirf TF-IDF (sparse) tha -- "rate limiter" vs
"throughput cap" jaise semantic matches miss hote the. Ab:

1. `OllamaEmbedder`: local Ollama `/api/embed` se dense embeddings
   (default model: nomic-embed-text, SALEHA_EMBED_MODEL se override)
2. TF-IDF SparseVectorEmbedder fallback (offline-safe, existing behavior)

VectorStore lazily decide karta hai: first index/search par dense probe;
fail ho to sparse pe graceful fallback. Dense vectors L2-normalized --
cosine = simple dot product.
"""

import json
import math
import os
import urllib.error
import urllib.request
from typing import List, Optional

DEFAULT_EMBED_MODEL = os.getenv("SALEHA_EMBED_MODEL", "nomic-embed-text")
DEFAULT_OLLAMA_BASE = os.getenv("SALEHA_OLLAMA_URL", "http://localhost:11434")
_EMBED_BATCH_SIZE = 32


class OllamaEmbedder:
    """Dense embedding backend via local Ollama /api/embed."""

    def __init__(self, model: str = DEFAULT_EMBED_MODEL,
                 base_url: str = DEFAULT_OLLAMA_BASE, timeout: int = 30):
        self.model = model
        self.embed_url = f"{base_url.rstrip('/')}/api/embed"
        self.timeout = timeout

    def available(self) -> bool:
        """Cheap probe: ek tiny embed request bhejo; 200 => usable."""
        try:
            vecs = self.embed_batch(["probe"])
            return bool(vecs and vecs[0])
        except Exception:
            return False

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Batch embed; normalized float vectors ya None (kisi bhi failure par)."""
        if not texts:
            return []
        out: List[List[float]] = []
        try:
            for i in range(0, len(texts), _EMBED_BATCH_SIZE):
                chunk = texts[i:i + _EMBED_BATCH_SIZE]
                payload = json.dumps({"model": self.model, "input": chunk}).encode("utf-8")
                req = urllib.request.Request(
                    self.embed_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                batch = data.get("embeddings")
                if not isinstance(batch, list) or len(batch) != len(chunk):
                    return None
                out.extend(batch)
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return None
        return [self._normalize(v) for v in out]

    @staticmethod
    def _normalize(vec: List[float]) -> List[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm <= 0:
            return vec
        return [x / norm for x in vec]


def dense_dot(v1: List[float], v2: List[float]) -> float:
    """Cosine similarity for (pre-normalized) dense vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))
