"""Unit tests for Hybrid BM25 + Vector Semantic Code Search Engine."""

from __future__ import annotations

import unittest
from saleha.core.semantic_search import SemanticSearchEngine, SearchResult


class SemanticSearchTests(unittest.TestCase):

    def setUp(self):
        self.engine = SemanticSearchEngine(root_dir=".")
        self.engine.index_codebase()

    def test_indexing_populates_documents(self):
        self.assertTrue(self.engine.is_indexed)
        self.assertGreater(self.engine._total_docs, 0)
        self.assertGreater(len(self.engine._doc_frequencies), 0)

    def test_tokenize_camel_and_snake_case(self):
        tokens = self.engine._tokenize("SemanticSearchEngine_with_astParser")
        self.assertIn("semantic", tokens)
        self.assertIn("search", tokens)
        self.assertIn("engine", tokens)
        self.assertIn("parser", tokens)

    def test_search_memory_compact_finds_results(self):
        results = self.engine.search("compact conversation history", top_k=5, semantic=True)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Should rank memory_store high
        matched_files = [r.file_path for r in results]
        self.assertTrue(any("memory_store" in f for f in matched_files))

    def test_search_git_worktree_finds_results(self):
        results = self.engine.search("create worktree isolated", top_k=5, semantic=True)
        self.assertGreater(len(results), 0)
        matched_files = [r.file_path for r in results]
        self.assertTrue(any("git_native" in f for f in matched_files))

    def test_lexical_vs_semantic_modes(self):
        lex_results = self.engine.search("SmartRouter", top_k=3, semantic=False)
        sem_results = self.engine.search("SmartRouter", top_k=3, semantic=True)
        self.assertGreater(len(lex_results), 0)
        self.assertGreater(len(sem_results), 0)
        self.assertEqual(lex_results[0].match_type, "bm25")
        self.assertEqual(sem_results[0].match_type, "hybrid")


if __name__ == "__main__":
    unittest.main()
