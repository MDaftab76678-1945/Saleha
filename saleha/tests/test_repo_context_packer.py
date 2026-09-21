"""
Tests for Saleha Core RepoContextPacker (saleha/core/repo_context_packer.py).

Verifies AST symbol extraction, tokenization, heuristic relevance scoring,
dynamic model-adaptive budgeting, and multi-file excerpt packing.
"""

from __future__ import annotations

import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
