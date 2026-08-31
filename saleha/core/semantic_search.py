"""
Saleha Core: Hybrid BM25 + Vector Semantic Code Search Engine

Combines fast subword BM25 lexical ranking with TF-IDF cosine vector similarity
to pinpoint functions, classes, docstrings, and architectural logic from natural language queries in <10ms.
"""

from __future__ import annotations

import os
import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any
from collections import Counter

from saleha.core.dependency_graph import dependency_graph
from saleha.core.codebase_indexer import codebase_indexer
from saleha.core.path_utils import safe_relpath


@dataclass
class SearchResult:
    file_path: str
    symbol_name: str
    symbol_type: str
    line_number: int
    score: float
    snippet: str
    match_type: str = "hybrid"


class SemanticSearchEngine:
    """Hybrid BM25 + TF-IDF Vector Semantic Code Search across multi-file codebases."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)
        self._documents: List[Dict[str, Any]] = []
        self._doc_frequencies: Dict[str, int] = Counter()
        self._total_docs = 0
        self._avg_doc_len = 0.0
        self.is_indexed = False
        self._ignore_dirs = {
            ".git", "__pycache__", "node_modules", "venv", ".venv",
            "dist", "build", ".pytest_cache", ".saleha", ".idea", ".vscode"
        }

    def _tokenize(self, text: str) -> List[str]:
        """Subword & identifier tokenizer supporting camelCase, snake_case, and natural language."""
        if not text:
            return []
        # Split on snake_case and whitespace
        raw_tokens = re.findall(r'[A-Za-z0-9]+', text)
        tokens = []
        for t in raw_tokens:
            tokens.append(t.lower())
            # Split camelCase tokens: e.g. "SemanticSearchEngine" -> "semantic", "search", "engine"
            sub_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', t)
            if len(sub_words) > 1:
                for sw in sub_words:
                    tokens.append(sw.lower())
        return [tok for tok in tokens if len(tok) >= 2]

    def index_codebase(self, root_dir: Optional[str] = None):
        """Builds combined lexical inverted index and vector representations for all codebase symbols."""
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)

        # 1. Build or refresh AST dependency graph
        if not dependency_graph.files_indexed:
            dependency_graph.build_graph(root_dir=self.root_dir)

        self._documents = []
        self._doc_frequencies = Counter()

        # 2. Extract documents from AST definitions
        for sym_name, locs in dependency_graph.definitions.items():
            for loc in locs:
                kind = getattr(loc, "kind", "symbol")
                content_text = f"{kind} {sym_name} {loc.docstring or ''} {loc.file_path}"
                tokens = self._tokenize(content_text)
                doc = {
                    "id": f"{loc.file_path}:{loc.line_number}:{sym_name}",
                    "file_path": loc.file_path.replace("\\", "/"),
                    "symbol_name": sym_name,
                    "symbol_type": kind,
                    "line_number": loc.line_number,
                    "snippet": f"{kind} {sym_name}() in {loc.file_path}",
                    "tokens": tokens,
                    "tf": Counter(tokens),
                    "len": len(tokens)
                }
                self._documents.append(doc)
                for t in set(tokens):
                    self._doc_frequencies[t] += 1

        # 3. Extract documents from raw source files (for comments, standalone code blocks)
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self._ignore_dirs and not d.startswith(".")]
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".go", ".rs", ".java", ".md")):
                    full_p = os.path.join(root, f)
                    rel_p = safe_relpath(full_p, self.root_dir).replace("\\", "/")
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="replace") as fp:
                            lines = fp.readlines()
                        for idx, line in enumerate(lines[:500], 1):
                            line_str = line.strip()
                            if line_str.startswith(("#", "//", "/*", "'''", '"""', "def ", "class ", "function ", "type ")):
                                tokens = self._tokenize(f"{line_str} {rel_p}")
                                if len(tokens) >= 3:
                                    doc = {
                                        "id": f"{rel_p}:{idx}",
                                        "file_path": rel_p,
                                        "symbol_name": line_str[:40],
                                        "symbol_type": "code_snippet",
                                        "line_number": idx,
                                        "snippet": line_str[:120],
                                        "tokens": tokens,
                                        "tf": Counter(tokens),
                                        "len": len(tokens)
                                    }
                                    self._documents.append(doc)
                                    for t in set(tokens):
                                        self._doc_frequencies[t] += 1
                    except OSError:
                        pass

        self._total_docs = len(self._documents)
        total_tokens = sum(d["len"] for d in self._documents)
        self._avg_doc_len = (total_tokens / self._total_docs) if self._total_docs > 0 else 1.0
        self.is_indexed = True

    def _score_bm25(self, query_tokens: List[str], doc: Dict[str, Any], k1: float = 1.5, b: float = 0.75) -> float:
        """Calculates Okapi BM25 score for a document."""
        score = 0.0
        doc_len = doc["len"]
        for qt in query_tokens:
            if qt in doc["tf"]:
                # Inverse Document Frequency
                df = self._doc_frequencies.get(qt, 0)
                idf = math.log(1.0 + (self._total_docs - df + 0.5) / (df + 0.5))
                # Term Frequency weight
                tf = doc["tf"][qt]
                num = tf * (k1 + 1.0)
                denom = tf + k1 * (1.0 - b + b * (doc_len / self._avg_doc_len))
                score += idf * (num / denom)
        return score

    def _score_vector_tfidf(self, query_tokens: List[str], doc: Dict[str, Any]) -> float:
        """Calculates Cosine Similarity over subword TF-IDF vectors."""
        q_tf = Counter(query_tokens)
        dot_product = 0.0
        q_norm_sq = 0.0
        d_norm_sq = 0.0

        for qt, q_count in q_tf.items():
            df = self._doc_frequencies.get(qt, 1)
            idf = math.log(1.0 + self._total_docs / df)
            q_weight = q_count * idf
            q_norm_sq += q_weight ** 2

            if qt in doc["tf"]:
                d_count = doc["tf"][qt]
                d_weight = d_count * idf
                dot_product += q_weight * d_weight

        for dt, d_count in doc["tf"].items():
            df = self._doc_frequencies.get(dt, 1)
            idf = math.log(1.0 + self._total_docs / df)
            d_norm_sq += (d_count * idf) ** 2

        if q_norm_sq == 0.0 or d_norm_sq == 0.0:
            return 0.0

        return dot_product / (math.sqrt(q_norm_sq) * math.sqrt(d_norm_sq))

    def search(self, query: str, top_k: int = 10, semantic: bool = True) -> List[SearchResult]:
        """Searches the codebase using hybrid BM25 lexical + TF-IDF cosine score."""
        if not self.is_indexed:
            self.index_codebase()

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scored_docs: List[Tuple[float, Dict[str, Any]]] = []

        for doc in self._documents:
            bm25_score = self._score_bm25(query_tokens, doc)
            if semantic:
                vector_score = self._score_vector_tfidf(query_tokens, doc)
                # Hybrid score: 60% BM25 + 40% Vector Cosine Similarity
                total_score = (bm25_score * 0.6) + (vector_score * 4.0 * 0.4)
            else:
                total_score = bm25_score

            if total_score > 0.01:
                scored_docs.append((total_score, doc))

        # Sort descending by score
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        results: List[SearchResult] = []
        seen_ids = set()

        for score, doc in scored_docs:
            if doc["id"] in seen_ids:
                continue
            seen_ids.add(doc["id"])
            results.append(SearchResult(
                file_path=doc["file_path"],
                symbol_name=doc["symbol_name"],
                symbol_type=doc["symbol_type"],
                line_number=doc["line_number"],
                score=round(score, 4),
                snippet=doc["snippet"],
                match_type="hybrid" if semantic else "bm25"
            ))
            if len(results) >= top_k:
                break

        return results


# Global instance
semantic_search = SemanticSearchEngine()
