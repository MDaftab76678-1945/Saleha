"""Tier B feature tests: embeddings, approval gate, metrics."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from saleha.core.vector_store import VectorStore
from saleha.core.embedding_backends import OllamaEmbedder, dense_dot
from saleha.core.approval_gate import approve, get_mode, requires_approval
from saleha.core.metrics import MetricsTracker


# ---------------- B1: Embeddings ----------------

class _FakeDenseEmbedder:
    """Deterministic 3-d vectors for testing (already normalized-ish)."""
    def __init__(self):
        self.map = {}
        self.available_called = 0

    def available(self):
        self.available_called += 1
        return True

    def embed_batch(self, texts):
        out = []
        for t in texts:
            if "lock" in t:
                out.append([1.0, 0.0, 0.0])
            elif "auth" in t:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


class DenseVectorStoreTests(unittest.TestCase):
    def test_dense_mode_ranks_semantically(self):
        emb = _FakeDenseEmbedder()
        vs = VectorStore(dense_embedder=emb)
        vs.add_documents([
            ("a", "redis lock", None),
            ("b", "jwt auth", None),
        ])
        hits = vs.search("distributed lock")
        self.assertEqual(vs.mode, "dense")
        self.assertEqual(hits[0].doc_id, "a")

    def test_fallback_to_sparse_when_dense_unavailable(self):
        bad = OllamaEmbedder()
        vs = VectorStore(dense_embedder=bad)
        with patch.object(bad, "available", return_value=False):
            vs.add_documents([("a", "redis lock", None)])
            hits = vs.search("lock")
        self.assertEqual(vs.mode, "sparse")
        self.assertEqual(hits[0].doc_id, "a")

    def test_mid_run_embed_failure_degrades_gracefully(self):
        emb = _FakeDenseEmbedder()

        def flaky(texts):
            if len(texts) > 1:
                return None  # reindex batch fail
            return [[0.0, 0.0, 1.0]] * len(texts)

        emb.embed_batch = flaky
        vs = VectorStore(dense_embedder=emb)
        vs.add_documents([("a", "one lock", None), ("b", "two auth", None)])
        hits = vs.search("lock")  # sparse fallback me keyword match kaam kare
        # degrade hoke sparse results hi diye, crash nahi
        self.assertEqual(hits[0].doc_id, "a")
        self.assertEqual(vs.mode, "sparse")

    def test_ollama_embedder_parses_payload(self):
        emb = OllamaEmbedder()

        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            status = 200
            def read(self_inner):
                return json.dumps({"embeddings": [[3.0, 4.0]]}).encode()

        with patch("urllib.request.urlopen", return_value=R()):
            vecs = emb.embed_batch(["hello"])
        self.assertEqual(vecs, [[0.6, 0.8]])  # normalized (3,4)->(.6,.8)

    def test_dense_dot_similarity(self):
        self.assertAlmostEqual(dense_dot([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(dense_dot([1, 0], [0, 1]), 0.0)


# ---------------- B2: Approval Gate ----------------

class ApprovalGateTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("SALEHA_APPROVAL", None)

    def test_default_mode_off_auto_approves_everything(self):
        os.environ.pop("SALEHA_APPROVAL", None)
        self.assertEqual(get_mode(), "off")
        self.assertTrue(approve("shell_exec", "rm something", confirmer=lambda p: False))

    def test_dangerous_mode_gates_only_dangerous_actions(self):
        os.environ["SALEHA_APPROVAL"] = "dangerous"
        denied = []
        ok = approve("shell_exec", "run build", confirmer=lambda p: denied.append(p) or False)
        self.assertFalse(ok)
        self.assertTrue(approve("read_docs", "harmless", confirmer=lambda p: False))

    def test_always_mode_gates_everything(self):
        os.environ["SALEHA_APPROVAL"] = "always"
        self.assertTrue(requires_approval("read_docs"))

    def test_approved_path_returns_true(self):
        os.environ["SALEHA_APPROVAL"] = "always"
        self.assertTrue(approve("git_commit", "msg", confirmer=lambda p: True))


# ---------------- B3: Metrics ----------------

class MetricsTests(unittest.TestCase):
    def _store(self, tmp):
        return MetricsTracker(os.path.join(tmp, "metrics.jsonl"))

    def test_record_and_tail_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = self._store(tmp)
            m.record("run_completed", success=True, attempts=2, model="m1", duration_sec=1.5)
            m.record("run_completed", success=False, attempts=3, model="m2", duration_sec=2.0)
            events = m.tail(10)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["attempts"], 2)

    def test_summary_math(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = self._store(tmp)
            m.record("run_completed", success=True, attempts=1, model="fast", duration_sec=1.0)
            m.record("run_completed", success=True, attempts=2, model="fast", duration_sec=3.0)
            m.record("run_completed", success=False, attempts=4, model="big", duration_sec=8.0)
            s = m.summary()
            self.assertEqual(s["total_runs"], 3)
            self.assertEqual(s["successful_runs"], 2)
            self.assertAlmostEqual(s["success_rate"], 66.7)
            self.assertAlmostEqual(s["avg_attempts"], 2.33, delta=0.01)
            self.assertEqual(s["by_model"]["fast"]["runs"], 2)
            self.assertEqual(s["by_model"]["fast"]["wins"], 2)
            self.assertAlmostEqual(s["avg_duration_sec"], 4.0)

    def test_empty_store_summary_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = self._store(tmp).summary()
            self.assertEqual(s["total_runs"], 0)
            self.assertEqual(s["success_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
