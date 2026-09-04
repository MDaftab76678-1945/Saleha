"""
Saleha Core: RAG Engineering Subsystem (2026 Frontier Standard)

Provides hybrid retrieval-augmented generation across codebases, token-budgeted
context packing, and reciprocal rank fusion:
- SemanticSearchEngine / semantic_search (Subword BM25 + TF-IDF lexical search)
- VectorStore / vector_store (Dense / Sparse local embeddings and cosine similarity)
- RepoContextPacker / repo_context_packer (Aider-style token-budgeted repo maps)
- TreeContextRanker / tree_context_ranker (Hierarchical tree relevance ranking)
- HybridRetriever (Reciprocal Rank Fusion (RRF) blending dense vector and BM25 signals)
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from saleha.core.semantic_search import SemanticSearchEngine, semantic_search, SearchResult
from saleha.core.vector_store import VectorStore, vector_store, VectorDocument, VectorSearchResult
from saleha.core.repo_context_packer import RepoContextPacker, repo_context_packer
from saleha.core.tree_context_ranker import TreeContextRanker, tree_context_ranker


@dataclass
class FusedRetrievalHit:
    doc_id: str
    text: str
    rrf_score: float
    bm25_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """
    State-of-the-art 2026 RAG Retrieval Engine using Reciprocal Rank Fusion (RRF).
    Fuses sparse lexical search (BM25) and dense embeddings to achieve high recall and precision.
    """

    def __init__(self, k_rrf: int = 60):
        self.k_rrf = k_rrf
        self.semantic = semantic_search
        self.vectors = vector_store

    def retrieve(self, query: str, top_k: int = 10) -> List[FusedRetrievalHit]:
        """Fuses BM25 results from semantic_search and dense results from vector_store."""
        # 1. Lexical BM25 search
        bm25_hits = self.semantic.search(query, top_k=top_k * 2)
        # 2. Vector search
        vector_hits = self.vectors.search(query, top_k=top_k * 2)

        rrf_scores: Dict[str, float] = {}
        bm25_ranks: Dict[str, int] = {}
        dense_ranks: Dict[str, int] = {}
        doc_texts: Dict[str, str] = {}
        doc_metas: Dict[str, Dict[str, Any]] = {}

        for rank, hit in enumerate(bm25_hits):
            doc_id = f"{hit.file_path}:{hit.symbol_name}"
            bm25_ranks[doc_id] = rank + 1
            doc_texts[doc_id] = hit.snippet
            doc_metas[doc_id] = {
                "file_path": hit.file_path,
                "symbol_name": hit.symbol_name,
                "line": hit.line_number,
            }
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (self.k_rrf + rank + 1)

        for rank, hit in enumerate(vector_hits):
            doc_id = hit.doc_id
            dense_ranks[doc_id] = rank + 1
            if doc_id not in doc_texts:
                doc_texts[doc_id] = hit.text
                doc_metas[doc_id] = hit.metadata
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (self.k_rrf + rank + 1)

        # Sort by final fused RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda d: rrf_scores[d], reverse=True)
        results = []
        for did in sorted_ids[:top_k]:
            results.append(
                FusedRetrievalHit(
                    doc_id=did,
                    text=doc_texts.get(did, ""),
                    rrf_score=round(rrf_scores[did], 5),
                    bm25_rank=bm25_ranks.get(did),
                    dense_rank=dense_ranks.get(did),
                    metadata=doc_metas.get(did, {}),
                )
            )
        return results


hybrid_retriever = HybridRetriever()


__all__ = [
    "SemanticSearchEngine",
    "semantic_search",
    "SearchResult",
    "VectorStore",
    "vector_store",
    "VectorDocument",
    "VectorSearchResult",
    "RepoContextPacker",
    "repo_context_packer",
    "TreeContextRanker",
    "tree_context_ranker",
    "HybridRetriever",
    "hybrid_retriever",
    "FusedRetrievalHit",
]
