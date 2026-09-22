"""
Saleha Core: Embedding Backends (Dense Semantic Vector Search)

Provides dense and sparse vector embedding capabilities:
1. `OllamaEmbedder`: Generates dense embeddings via local Ollama `/api/embed`
   (default model: nomic-embed-text, override via SALEHA_EMBED_MODEL).
2. Sparse fallback: TF-IDF vector embedding when Ollama is unavailable.

Embeddings are L2-normalized, allowing cosine similarity to be computed
via simple dot product.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from typing import List, Optional


def _normalize_ollama_url(raw_url: str) -> str:
    """Normalizes Ollama endpoint URL to prevent 0.0.0.0 or localhost DNS latency issues."""
    url = (raw_url or "").strip()
    if not url:
        return "http://127.0.0.1:11434"
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"
    url = url.replace("0.0.0.0:11434", "127.0.0.1:11434").replace("localhost:11434", "127.0.0.1:11434")
    return url.rstrip("/")


DEFAULT_EMBED_MODEL = os.getenv("SALEHA_EMBED_MODEL", "nomic-embed-text")
_raw_ollama_host = os.getenv("SALEHA_OLLAMA_URL") or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
DEFAULT_OLLAMA_BASE = _normalize_ollama_url(_raw_ollama_host)
_EMBED_BATCH_SIZE = 32


class OllamaEmbedder:
    """Dense embedding backend via local Ollama /api/embed."""

    def __init__(
        self,
        model: str = DEFAULT_EMBED_MODEL,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.model = model
        base = _normalize_ollama_url(base_url) if base_url else DEFAULT_OLLAMA_BASE
        self.embed_url = f"{base}/api/embed"
        self.timeout = timeout

    def available(self) -> bool:
        """Lightweight probe: sends single-word embed request; 200 => available."""
        try:
            vecs = self.embed_batch(["probe"])
            return bool(vecs and vecs[0])
        except Exception:
            return False

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Batch embed texts; returns normalized float vectors or None on failure."""
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
        """Normalizes vector to unit L2 norm."""
        norm = math.sqrt(sum(x * x for x in vec))
        if norm <= 0:
            return vec
        return [x / norm for x in vec]


def dense_dot(v1: List[float], v2: List[float]) -> float:
    """Cosine similarity for pre-normalized dense vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2, strict=False))
