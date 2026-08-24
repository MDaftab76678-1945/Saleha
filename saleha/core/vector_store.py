"""
Saleha Core: Semantic Vector Store & Local RAG Engine

Zero-dependency local vector store using subword n-gram TF-IDF embeddings
and Cosine Similarity for fast, accurate semantic search across codebases,
past solutions, and architectural patterns.
"""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

from saleha.core.embedding_backends import dense_dot as dense_cosine


@dataclass
class VectorDocument:
    doc_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Dict[str, float] = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    doc_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class SparseVectorEmbedder:
    """Subword character n-gram + word token TF-IDF embedder."""

    def __init__(self, ngram_range: Tuple[int, int] = (3, 5)):
        self.ngram_range = ngram_range
        self.doc_count: int = 0
        self.term_doc_freq: Dict[str, int] = defaultdict(int)

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        for w in words:
            tokens.append(w)
            # Add character n-grams for code and subword semantic matching
            if len(w) >= self.ngram_range[0]:
                for n in range(self.ngram_range[0], min(len(w) + 1, self.ngram_range[1] + 1)):
                    for i in range(len(w) - n + 1):
                        tokens.append(w[i:i + n])
        return tokens

    def fit(self, texts: List[str]):
        """Fits vocabulary and computes Document Frequencies."""
        self.doc_count = len(texts)
        self.term_doc_freq.clear()
        for text in texts:
            unique_terms = set(self._tokenize(text))
            for term in unique_terms:
                self.term_doc_freq[term] += 1

    def embed(self, text: str) -> Dict[str, float]:
        """Generates L2-normalized TF-IDF vector."""
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        term_counts = Counter(tokens)
        total_terms = len(tokens)
        vector = {}

        for term, count in term_counts.items():
            tf = count / total_terms
            df = self.term_doc_freq.get(term, 1)
            idf = math.log((1 + self.doc_count) / (1 + df)) + 1.0
            vector[term] = tf * idf

        # L2 Normalization
        norm = math.sqrt(sum(val * val for val in vector.values()))
        if norm > 0:
            for term in vector:
                vector[term] /= norm

        return vector


def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Computes cosine similarity between two sparse unit vectors."""
    if not v1 or not v2:
        return 0.0
    # Dot product of smaller vector against larger
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(weight * v2.get(term, 0.0) for term, weight in v1.items())


class VectorStore:
    """In-memory Vector Database for local RAG retrieval.

    Naya (B1): embedding backend LAZILY choose hota hai --
      1. Dense (Ollama nomic-embed-text) available ho to semantic quality zyada
      2. Warna legacy TF-IDF sparse fallback (offline-safe)
    Mode switch hone par poora index dirty mark hota hai (re-embed).
    Mutations sirf `_dirty` flag set karte hain; reindex next search par ek baar.
    """

    def __init__(self, enable_dense: bool = True, dense_embedder=None):
        self.embedder = SparseVectorEmbedder()
        self.documents: Dict[str, VectorDocument] = {}
        self._dirty = False
        self.mode = "sparse"  # "dense" | "sparse" (resolved lazily)
        self._mode_resolved = False
        self.enable_dense = enable_dense
        self.dense_embedder = dense_embedder  # lazy init on first reindex if None

    def _resolve_mode(self) -> str:
        """Ek hi baar probe karke embedding mode decide karta hai."""
        if self._mode_resolved:
            return self.mode
        self._mode_resolved = True
        if not self.enable_dense:
            self.mode = "sparse"
            return self.mode
        try:
            from saleha.core.embedding_backends import OllamaEmbedder
            embedder = self.dense_embedder or OllamaEmbedder()
            if embedder.available():
                self.mode = "dense"
                self.dense_embedder = embedder
        except Exception:
            self.mode = "sparse"
        return self.mode

    def add_document(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        self.documents[doc_id] = VectorDocument(doc_id=doc_id, text=text, metadata=metadata or {})
        self._dirty = True

    def add_documents(self, docs: List[Tuple[str, str, Optional[Dict[str, Any]]]]):
        for doc_id, text, meta in docs:
            self.documents[doc_id] = VectorDocument(doc_id=doc_id, text=text, metadata=meta or {})
        if docs:
            self._dirty = True

    def remove_document(self, doc_id: str) -> bool:
        """Single document ko remove karta hai (incremental delete)."""
        if doc_id in self.documents:
            del self.documents[doc_id]
            self._dirty = True
            return True
        return False

    def _reindex(self):
        all_docs = list(self.documents.values())
        if not all_docs:
            return

        if self._resolve_mode() == "dense":
            vectors = self.dense_embedder.embed_batch([d.text for d in all_docs])
            if vectors is not None and len(vectors) == len(all_docs):
                for doc, vec in zip(all_docs, vectors):
                    doc.vector = vec
                return
            # Dense fail hua (Ollama band ho gaya?) -> sparse pe degrade
            self.mode = "sparse"

        # Sparse path (legacy TF-IDF)
        self.embedder.fit([d.text for d in all_docs])
        for doc in all_docs:
            doc.vector = self.embedder.embed(doc.text)

    def _ensure_index(self):
        if self._dirty:
            self._reindex()
            self._dirty = False

    def search(self, query: str, top_k: int = 5, min_score: float = 0.01) -> List[VectorSearchResult]:
        if not self.documents:
            return []
        self._ensure_index()

        if self.mode == "dense":
            query_vecs = self.dense_embedder.embed_batch([query])
            if query_vecs and query_vecs[0]:
                query_vec = query_vecs[0]
            else:
                return []
            results = []
            for doc in self.documents.values():
                score = dense_cosine(query_vec, doc.vector)
                if score >= min_score:
                    results.append(VectorSearchResult(
                        doc_id=doc.doc_id, text=doc.text,
                        score=round(score, 4), metadata=doc.metadata,
                    ))
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]

        # Sparse path
        query_vec = self.embedder.embed(query)
        if not query_vec:
            return []

        results = []
        for doc in self.documents.values():
            score = cosine_similarity(query_vec, doc.vector)
            if score >= min_score:
                results.append(VectorSearchResult(
                    doc_id=doc.doc_id,
                    text=doc.text,
                    score=score,
                    metadata=doc.metadata
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def count(self) -> int:
        return len(self.documents)

    def clear(self):
        self.documents.clear()
        self._dirty = False

