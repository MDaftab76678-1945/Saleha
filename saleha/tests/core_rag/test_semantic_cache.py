"""
Tests for the semantic prompt cache.

What this replaces: the notebook's version, wired to

    def get_embedding(text): return np.random.rand(384).astype(np.float32)

Measured with 384-dim uniform random vectors (pairwise cosine ~0.73-0.77
regardless of the text):

    threshold 0.70 -> an unrelated query is served the cached answer
    threshold 0.95 -> even an identical prompt misses

Both failure modes are asserted below, because "it uses random vectors" is a
claim and this is the evidence.

Verified separately against the real embedder (nomic-embed-text via Ollama):
exact 1.000, paraphrase 0.966 (hit), different task below threshold (miss).
Those runs are recorded here, not asserted -- a test that needs a model
installed is a flake.
"""

from __future__ import annotations

import math
import random
import unittest
import zlib
from typing import List, Optional

from saleha.core.rag.semantic_cache import (
    DEFAULT_THRESHOLD,
    SemanticCache,
    cosine,
    literals,
)


class WordVectorEmbedder:
    """Deterministic bag-of-words embedder: real signal, no network."""

    def __init__(self, dims: int = 128) -> None:
        self.dims: int = dims
        self.calls: int = 0

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self.calls += 1
        out: List[List[float]] = []
        for text in texts:
            vector = [0.0] * self.dims
            for word in (text or "").lower().split():
                vector[zlib.crc32(word.encode("utf-8")) % self.dims] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            out.append([x / norm for x in vector])
        return out


class RandomEmbedder:
    """The notebook's version, reproduced to pin its failure modes."""

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for _ in texts:
            vector = [random.random() for _ in range(384)]
            norm = math.sqrt(sum(x * x for x in vector))
            out.append([x / norm for x in vector])
        return out


class DeadEmbedder:
    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        return None


class RandomVectorsAreBrokenTests(unittest.TestCase):
    """The defect this module exists to fix, asserted rather than described."""

    def test_permissive_threshold_serves_an_unrelated_answer(self) -> None:
        # Seeded, not because a favorable seed was hand-picked, but because
        # this test is inherently statistical (unit-normalized uniform
        # vectors) and an unseeded RNG makes it a genuine, measured flake:
        # a direct 200-trial sample landed below 0.70 about 0.5% of the
        # time even though the mean sits at ~0.75 (see module docstring).
        # Any fixed seed demonstrates the real defect on every run instead
        # of failing to demonstrate it on an unlucky one.
        random.seed(1234567890)
        cache = SemanticCache(embedder=RandomEmbedder(), threshold=0.70,
                              strict=False)
        cache.put("reverse a string", "REVERSE_ANSWER")
        hit = cache.get("how do I configure nginx")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.response, "REVERSE_ANSWER")   # wrong answer served

    def test_strict_threshold_misses_even_an_identical_prompt(self) -> None:
        cache = SemanticCache(embedder=RandomEmbedder(), threshold=0.95,
                              strict=False)
        cache.put("reverse a string", "ANSWER")
        self.assertIsNone(cache.get("reverse a string"))

    def test_a_real_embedder_does_neither(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), threshold=0.9)
        cache.put("reverse a string please", "ANSWER")
        self.assertIsNotNone(cache.get("reverse a string please"))
        self.assertIsNone(cache.get("configure the nginx web server"))


class MatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = SemanticCache(embedder=WordVectorEmbedder(),
                                   threshold=0.9)
        self.cache.put("write a function to reverse a string",
                       "def rev(s): return s[::-1]", model="m")

    def test_identical_prompt_hits(self) -> None:
        hit = self.cache.get("write a function to reverse a string", model="m")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertAlmostEqual(hit.similarity, 1.0, places=5)

    def test_a_different_task_misses(self) -> None:
        self.assertIsNone(
            self.cache.get("write a function to sort a list of numbers",
                           model="m"))

    def test_a_hit_reports_what_it_matched(self) -> None:
        hit = self.cache.get("write a function to reverse a string", model="m")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertIn("reverse", hit.matched_prompt)
        self.assertIn("semantic cache hit", hit.describe())

    def test_another_models_answer_is_not_served(self) -> None:
        """memory_store.recall() had exactly this bug once."""
        self.assertIsNone(
            self.cache.get("write a function to reverse a string",
                           model="different-model"))

    def test_empty_prompt_misses(self) -> None:
        self.assertIsNone(self.cache.get(""))


class LiteralGuardTests(unittest.TestCase):
    """Embeddings are worst at exactly the details that change the answer."""

    def test_different_numbers_block_a_hit(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), threshold=0.5)
        cache.put("retry the request 3 times", "use 3", model="m")
        self.assertIsNone(cache.get("retry the request 30 times", model="m"))
        self.assertEqual(cache.stats()["rejected_by_literals"], 1)

    def test_different_file_paths_block_a_hit(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), threshold=0.5)
        cache.put("add a test to parser.py", "...", model="m")
        self.assertIsNone(cache.get("add a test to router.py", model="m"))

    def test_strict_false_allows_the_match(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), threshold=0.5,
                              strict=False)
        cache.put("retry the request 3 times", "use 3", model="m")
        self.assertIsNotNone(cache.get("retry the request 30 times", model="m"))

    def test_literals_extracts_numbers_quotes_and_paths(self) -> None:
        numbers, quoted, paths = literals(
            "set timeout to 30 and write 'hello' into config.py")
        self.assertIn("30", numbers)
        self.assertIn("hello", quoted)
        self.assertIn("config.py", paths)

    def test_identical_literals_do_not_block(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), threshold=0.5)
        cache.put("retry 3 times", "answer", model="m")
        self.assertIsNotNone(cache.get("retry 3 times", model="m"))


class DegradationTests(unittest.TestCase):
    """No embedder must mean 'no cache', never 'wrong answers'."""

    def test_put_refuses_when_it_cannot_embed(self) -> None:
        cache = SemanticCache(embedder=DeadEmbedder())
        self.assertFalse(cache.put("prompt", "response"))
        self.assertEqual(cache.stats()["entries"], 0)

    def test_get_misses_when_it_cannot_embed(self) -> None:
        cache = SemanticCache(embedder=DeadEmbedder())
        self.assertIsNone(cache.get("prompt"))

    def test_available_is_a_real_probe(self) -> None:
        self.assertFalse(SemanticCache(embedder=DeadEmbedder()).available())
        self.assertTrue(SemanticCache(embedder=WordVectorEmbedder()).available())

    def test_a_raising_embedder_does_not_propagate(self) -> None:
        class Boom:
            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                raise RuntimeError("embedder exploded")

        cache = SemanticCache(embedder=Boom())
        self.assertFalse(cache.put("p", "r"))
        self.assertIsNone(cache.get("p"))

    def test_empty_response_is_not_stored(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder())
        self.assertFalse(cache.put("prompt", ""))


class BookkeepingTests(unittest.TestCase):
    def test_eviction_is_oldest_first(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), max_entries=2,
                              threshold=0.9)
        cache.put("alpha one", "1")
        cache.put("beta two", "2")
        cache.put("gamma three", "3")
        self.assertEqual(cache.stats()["entries"], 2)
        self.assertIsNone(cache.get("alpha one"))

    def test_stats_track_hits_and_misses(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder(), threshold=0.9)
        cache.put("hello world", "x")
        cache.get("hello world")
        cache.get("completely different subject matter")
        stats = cache.stats()
        self.assertEqual((stats["hits"], stats["misses"]), (1, 1))
        self.assertEqual(stats["hit_rate"], 0.5)

    def test_clear_resets_everything(self) -> None:
        cache = SemanticCache(embedder=WordVectorEmbedder())
        cache.put("hello world", "x")
        cache.get("hello world")
        cache.clear()
        self.assertEqual(cache.stats()["entries"], 0)
        self.assertEqual(cache.stats()["hits"], 0)

    def test_default_threshold_is_strict(self) -> None:
        """A loose default is how a cache starts answering the wrong question."""
        self.assertGreaterEqual(DEFAULT_THRESHOLD, 0.9)

    def test_cosine_handles_mismatched_and_empty_vectors(self) -> None:
        self.assertEqual(cosine([], [1.0]), 0.0)
        self.assertEqual(cosine([1.0, 0.0], [1.0]), 0.0)
        self.assertAlmostEqual(cosine([1.0, 0.0], [1.0, 0.0]), 1.0)


if __name__ == "__main__":
    unittest.main()
