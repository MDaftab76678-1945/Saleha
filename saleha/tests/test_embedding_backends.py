"""Unit Tests for EmbeddingBackends (OllamaEmbedder, Vector Normalization, Dense Dot Product).

Validates vector normalization, cosine similarity computation, URL normalization,
and Ollama batch embedding error resilience.
"""

from __future__ import annotations

import json
import math
import unittest
from io import BytesIO
from typing import List, Optional
from unittest.mock import patch, MagicMock

from saleha.core.rag.embedding_backends import (
    OllamaEmbedder,
    dense_dot,
    _normalize_ollama_url,
)


class TestEmbeddingBackends(unittest.TestCase):
    """Test suite for embedding_backends module."""

    def test_normalize_unit_vector(self) -> None:
        vec: List[float] = [3.0, 4.0]
        norm_vec: List[float] = OllamaEmbedder._normalize(vec)
        self.assertAlmostEqual(norm_vec[0], 0.6)
        self.assertAlmostEqual(norm_vec[1], 0.8)
        # Unit length
        length = math.sqrt(sum(x * x for x in norm_vec))
        self.assertAlmostEqual(length, 1.0)

    def test_normalize_zero_vector(self) -> None:
        zero_vec: List[float] = [0.0, 0.0, 0.0]
        self.assertEqual(OllamaEmbedder._normalize(zero_vec), zero_vec)

    def test_dense_dot_identical_and_orthogonal(self) -> None:
        v1: List[float] = [1.0, 0.0]
        v2: List[float] = [1.0, 0.0]
        self.assertAlmostEqual(dense_dot(v1, v2), 1.0)

        v3: List[float] = [0.0, 1.0]
        self.assertAlmostEqual(dense_dot(v1, v3), 0.0)

        v4: List[float] = [-1.0, 0.0]
        self.assertAlmostEqual(dense_dot(v1, v4), -1.0)

    def test_dense_dot_mismatched_and_empty(self) -> None:
        self.assertEqual(dense_dot([], [1.0]), 0.0)
        self.assertEqual(dense_dot([1.0], []), 0.0)
        self.assertEqual(dense_dot([1.0, 2.0], [1.0]), 0.0)

    def test_normalize_ollama_url(self) -> None:
        # Default/empty
        self.assertEqual(_normalize_ollama_url(""), "http://127.0.0.1:11434")
        # 0.0.0.0 rewrite
        self.assertEqual(_normalize_ollama_url("http://0.0.0.0:11434/"), "http://127.0.0.1:11434")
        # localhost rewrite
        self.assertEqual(_normalize_ollama_url("http://localhost:11434"), "http://127.0.0.1:11434")
        # Custom host preserved
        self.assertEqual(_normalize_ollama_url("http://remote-server:11434/"), "http://remote-server:11434")

    def test_embed_batch_empty_input(self) -> None:
        embedder = OllamaEmbedder()
        self.assertEqual(embedder.embed_batch([]), [])

    def test_embed_batch_mocked_success(self) -> None:
        embedder = OllamaEmbedder()
        mock_response = MagicMock()
        mock_payload = json.dumps({"embeddings": [[0.5, 0.5]]}).encode("utf-8")
        mock_response.read.return_value = mock_payload
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            res = embedder.embed_batch(["hello world"])
            self.assertIsNotNone(res)
            self.assertEqual(len(res), 1)  # type: ignore[arg-type]
            # Verify result is normalized
            norm = math.sqrt(sum(x * x for x in res[0]))  # type: ignore[index]
            self.assertAlmostEqual(norm, 1.0)

    def test_embed_batch_network_error_returns_none(self) -> None:
        embedder = OllamaEmbedder()
        with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
            res = embedder.embed_batch(["hello world"])
            self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
