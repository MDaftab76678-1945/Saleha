"""
Tests for Saleha Core RepoContextPacker (saleha/core/repo_context_packer.py).

Verifies AST symbol extraction, tokenization, heuristic relevance scoring,
dynamic model-adaptive budgeting, and multi-file excerpt packing.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from typing import List, Optional

from saleha.core.rag.repo_context_packer import (
    RepoContextPacker,
    _python_symbols,
    _tokenize,
)


class RepoContextPackerTokenizerTests(unittest.TestCase):
    def test_tokenize_splits_camel_case_and_snake_case(self) -> None:
        tokens = _tokenize("parseConfigFile payment_processor_v2")
        self.assertIn("parse", tokens)
        self.assertIn("config", tokens)
        self.assertIn("file", tokens)
        self.assertIn("payment", tokens)
        self.assertIn("processor", tokens)

    def test_tokenize_filters_common_stopwords(self) -> None:
        tokens = _tokenize("create a service with the database and make it work")
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertNotIn("with", tokens)
        self.assertNotIn("create", tokens)
        self.assertIn("service", tokens)
        self.assertIn("database", tokens)


class RepoContextPackerSymbolExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_python_symbols_extracts_classes_sync_and_async_defs(self) -> None:
        file_path = os.path.join(self.root, "sample.py")
        code = (
            'class UserRegistry:\n'
            '    """Manages user persistence."""\n'
            '    def __init__(self):\n'
            '        pass\n\n'
            '    async def fetch_user(self, uid: str):\n'
            '        """Asynchronously fetch user profile."""\n'
            '        return {}\n'
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        symbols = _python_symbols(file_path)
        # Expected: UserRegistry (class), __init__ (def), fetch_user (async def)
        names = [s[2] for s in symbols]
        kinds = [s[1] for s in symbols]
        docs = [s[3] for s in symbols]

        self.assertIn("UserRegistry", names)
        self.assertIn("fetch_user", names)
        self.assertIn("class", kinds)
        self.assertIn("async def", kinds)
        self.assertIn("Manages user persistence.", docs)
        self.assertIn("Asynchronously fetch user profile.", docs)


class RepoContextPackerScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.packer = RepoContextPacker(root_dir=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_file(self, rel_path: str, content: str) -> str:
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return full

    def test_scoring_prioritizes_src_over_test_fixtures(self) -> None:
        src_path = self._write_file(
            "src/circuit_breaker.py",
            "class CircuitBreaker:\n    def execute(self): pass\n",
        )
        test_path = self._write_file(
            "tests/test_circuit_breaker.py",
            "class CircuitBreakerTest:\n    def test_execute(self): pass\n",
        )
        tokens = _tokenize("circuit breaker execute")
        score_src, _ = self.packer._score_file(src_path, tokens)
        score_test, _ = self.packer._score_file(test_path, tokens)
        self.assertGreater(score_src, score_test)

    def test_application_entry_points_receive_score_boost(self) -> None:
        entry_path = self._write_file("main.py", "def run(): pass\n")
        helper_path = self._write_file("util.py", "def run(): pass\n")
        tokens = _tokenize("run")
        score_entry, _ = self.packer._score_file(entry_path, tokens)
        score_helper, _ = self.packer._score_file(helper_path, tokens)
        self.assertGreater(score_entry, score_helper)


class RepoContextPackerPackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.packer = RepoContextPacker(root_dir=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_file(self, rel_path: str, content: str) -> str:
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return full

    def test_pack_empty_repository_returns_empty_string(self) -> None:
        ctx = self.packer.pack("build authorization layer")
        self.assertEqual(ctx, "")

    def test_pack_model_adaptive_dynamic_budget(self) -> None:
        self._write_file("src/auth.py", "class AuthManager:\n    def verify(self): pass\n" * 30)
        self._write_file("src/tokens.py", "class TokenStore:\n    def issue(self): pass\n" * 30)

        # 3b model gets a safe proportional budget
        ctx_3b = self.packer.pack("verify auth tokens", model="qwen2.5-coder:3b")
        # 8b model gets a larger proportional budget
        ctx_8b = self.packer.pack("verify auth tokens", model="qwen3:8b")

        self.assertIn("## Repository Context", ctx_3b)
        self.assertIn("### Project Layout", ctx_3b)
        self.assertIn("### Task-Relevant Symbols", ctx_3b)
        self.assertIn("auth.py", ctx_3b)
        self.assertGreaterEqual(len(ctx_8b), len(ctx_3b))

    def test_pack_multi_file_excerpts_when_budget_allows(self) -> None:
        self._write_file("src/crypto_service.py", "class CryptoService:\n    def hash(self): pass\n")
        self._write_file("src/crypto_keys.py", "class KeyStore:\n    def load(self): pass\n")

        ctx = self.packer.pack(
            "crypto hash keys service",
            budget_chars=12000,
            max_excerpts=2,
        )
        self.assertIn("### Key File Excerpt: src/crypto_service.py", ctx)
        self.assertIn("### Key File Excerpt: src/crypto_keys.py", ctx)

    def test_pack_strict_character_budget_discipline(self) -> None:
        for i in range(20):
            self._write_file(f"src/module_{i}.py", f"class Handler{i}:\n    def handle(self): pass\n" * 20)

        budget = 2000
        ctx = self.packer.pack("handle module requests", budget_chars=budget)
        self.assertLessEqual(len(ctx), budget + 200)


class _FakeEmbedder:
    """Maps text to a 2-d vector by which topic word it mentions.

    "money" texts point one way, "network" texts the other, so a task can be
    semantically close to a file it shares no keyword with.
    """

    model = "fake-embed"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.embedded: List[str] = []

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        if self.fail:
            return None
        self.embedded.extend(texts)
        out = []
        for t in texts:
            low = t.lower()
            if any(w in low for w in ("invoice", "refund", "charge", "billing")):
                out.append([1.0, 0.0])
            else:
                out.append([0.0, 1.0])
        return out


class _LoudRanker:
    """A symbol ranker whose popularity boost favours one file hugely."""

    def __init__(self, favourite: str) -> None:
        self.favourite = favourite

    def popularity_boost(self) -> dict:
        return {self.favourite: 600.0}


class RepoContextPackerRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_file(self, rel_path: str, content: str) -> None:
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    def test_build_output_and_extra_venvs_are_not_scanned(self) -> None:
        self._write_file("src/auth.py", "def verify_token(): pass\n")
        self._write_file("apps/web/.next/static/chunks/main.js", "function verify_token(){}\n")
        self._write_file(".venv_laya/lib/auth.py", "def verify_token(): pass\n")
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=None, semantic=False)
        paths = [sf.path for sf in packer.rank_files("verify token")]
        self.assertEqual(paths, ["src/auth.py"])

    def test_popularity_cannot_lift_an_unmatched_file_over_a_match(self) -> None:
        self._write_file("src/auth.py", "def verify_token(): pass\n")
        self._write_file("src/hub.py", "def unrelated_helper(): pass\n")
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=_LoudRanker("src/hub.py"),
                                   semantic=False)
        ranked = packer.rank_files("verify token")
        self.assertEqual(ranked[0].path, "src/auth.py")
        hub = next(sf for sf in ranked if sf.path == "src/hub.py")
        self.assertEqual(hub.score, 0.0)

    def test_semantic_ranking_finds_a_file_with_no_shared_keyword(self) -> None:
        self._write_file("src/ledger.py", "def post_invoice(): pass\n")
        self._write_file("src/sockets.py", "def open_customer_socket(): pass\n")
        emb = _FakeEmbedder()
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=None, embedder=emb)
        task = "we were billing twice, give the money back"
        keyword_only = RepoContextPacker(root_dir=self.root, symbol_ranker=None, semantic=False)
        # No shared word: the keyword scorer alone scores every file zero.
        self.assertTrue(all(sf.score == 0 for sf in keyword_only.rank_files(task)))
        ranked = packer.rank_files(task)
        self.assertEqual(packer.last_ranking, "keyword+semantic")
        self.assertEqual(ranked[0].path, "src/ledger.py")
        self.assertGreater(ranked[0].score, 0)

    def test_unchanged_files_are_not_embedded_twice(self) -> None:
        self._write_file("src/ledger.py", "def post_invoice(): pass\n")
        emb = _FakeEmbedder()
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=None, embedder=emb)
        packer.rank_files("refund an invoice")
        first = len(emb.embedded)
        RepoContextPacker(root_dir=self.root, symbol_ranker=None,
                          embedder=emb).rank_files("refund an invoice")
        # Second packer: only the query is embedded; the file comes from the cache.
        self.assertEqual(len(emb.embedded) - first, 1)

    def test_unreachable_embedder_falls_back_and_says_so(self) -> None:
        self._write_file("src/auth.py", "def verify_token(): pass\n")
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=None,
                                   embedder=_FakeEmbedder(fail=True))
        ranked = packer.rank_files("verify token")
        self.assertEqual(packer.last_ranking, "keyword")
        self.assertIn("unreachable", packer.last_ranking_note)
        self.assertEqual(ranked[0].path, "src/auth.py")

    def test_semantic_is_off_by_default(self) -> None:
        packer = RepoContextPacker(root_dir=self.root, symbol_ranker=None)
        self.assertFalse(packer.semantic)
        self.assertEqual(packer.last_ranking_note, "semantic ranking disabled")


if __name__ == "__main__":
    unittest.main()
