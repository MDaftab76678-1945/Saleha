"""
v0.6.0 feature tests:
- RepoContextPacker: scoring, budget, skip-dirs
- TeamOrchestrator on_event real-time streaming callback
- Memory Store incremental vector updates (no full resync per save)
- VectorStore lazy reindex + remove_document
- execution_policy.ensure_image preflight
"""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from saleha.core.repo_context_packer import RepoContextPacker
from saleha.core.vector_store import VectorStore
from saleha.core.memory_store import MemoryStore


class RepoContextPackerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel: str, content: str):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_relevant_file_ranks_first_and_appears_in_output(self):
        self._write("src/payments.py", "class PaymentProcessor:\n    def charge(self, amount): ...\n")
        self._write("src/unrelated.py", "def render_menu(): ...\n")
        packer = RepoContextPacker(root_dir=self.root)
        ctx = packer.pack("implement token bucket rate limiter for payments")
        # payments.py symbols/path task tokens se match karte hain -- excerpt wahi mile
        self.assertIn("Repository Context", ctx)
        self.assertIn("payments.py", ctx)

    def test_budget_is_respected(self):
        big = "def filler_%d(): pass\n" * 1  # small lines; use many files instead
        for i in range(50):
            self._write(f"src/mod_{i}.py", f"class Thing{i}:\n    def process(self): ...\n" * 30)
        packer = RepoContextPacker(root_dir=self.root)
        ctx = packer.pack("process things", budget_chars=1500)
        self.assertLessEqual(len(ctx), 1600)

    def test_skip_dirs_ignored(self):
        self._write("venv/lib/junk.py", "class RateLimiter:\n    pass\n")
        self._write("app/core.py", "class RateLimiter:\n    pass\n")
        packer = RepoContextPacker(root_dir=self.root)
        stats = packer.stats()
        self.assertEqual(stats["code_files"], 1)

    def test_empty_repo_returns_empty_string(self):
        packer = RepoContextPacker(root_dir=self.root)
        self.assertEqual(packer.pack("anything"), "")

    def test_non_code_files_excluded(self):
        self._write("notes.txt", "rate limiter class here")
        packer = RepoContextPacker(root_dir=self.root)
        self.assertEqual(packer.stats()["code_files"], 0)


class _FakeStageAgent:
    """Minimal think() stub returning canned stage content."""

    def __init__(self, marker):
        self.marker = marker

    def think(self, prompt, **kwargs):
        resp = MagicMock()
        resp.success = True
        resp.content = f"{self.marker} output"
        return resp


class EventStreamingTests(unittest.TestCase):
    def test_on_event_fires_per_stage_immediately(self):
        from saleha.core.team_orchestrator import TeamOrchestrator

        orch = TeamOrchestrator(model="test-model")
        events = []

        fake_agents = {
            "agent_product_manager": _FakeStageAgent("PRD"),
            "agent_software_designer": _FakeStageAgent("DESIGN"),
            "agent_security_engineer": _FakeStageAgent("SEC"),
            "agent_test_automation_engineer": _FakeStageAgent("QA"),
        }
        # Implementation agent ko alag marker (code fence chahiye)
        impl_agent = _FakeStageAgent("IMPL")
        orig_impl_think = impl_agent.think

        def impl_think(prompt, **kwargs):
            resp = orig_impl_think(prompt)
            resp.content = "```python\nvalue = 42\n```"
            return resp

        impl_agent.think = impl_think

        def fake_get_agent(profile_id, default_role_name):
            if profile_id == "agent_software_engineer":
                return impl_agent
            return fake_agents[profile_id]

        with patch.object(orch, "_get_agent", side_effect=fake_get_agent), \
             patch.object(orch.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(
                success=True, blocked=False, output="OK", error=""
            )
            result = orch.run_team_workflow(
                "Test goal",
                on_event=lambda ev: events.append(ev),
            )

        self.assertTrue(result.success)
        stage_names = [e["stage"] for e in events]
        self.assertEqual(stage_names[0], "Product Manager (PRD)")
        self.assertIn("Senior SDE (Implementation)", stage_names)
        self.assertEqual(events[-1]["stage"], "Verification (Execution)")
        # Har event me stage_index monotonic hai
        indexes = [e["stage_index"] for e in events]
        self.assertEqual(indexes, sorted(indexes))

    def test_no_callback_still_works(self):
        from saleha.core.team_orchestrator import TeamOrchestrator

        orch = TeamOrchestrator(model="test-model")
        with patch.object(orch, "_get_agent", return_value=_FakeStageAgent("X")), \
             patch.object(orch.executor, "execute") as mock_exec:
            mock_exec.return_value = MagicMock(success=True, blocked=False, output="", error="")
            result = orch.run_team_workflow("goal")
        self.assertTrue(result.success)


class IncrementalMemoryTests(unittest.TestCase):
    def _store(self, tmp):
        return MemoryStore(storage_path=os.path.join(tmp, "mem.json"))

    def test_remember_does_not_resync_all_vectors_each_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            calls = []
            original = store.vector_store._reindex
            with patch.object(store.vector_store, "_reindex",
                              side_effect=lambda: (calls.append(1), original())):
                for i in range(20):
                    store.remember(f"unique goal number {i}", "print(1)")
            # Pehle har remember par FULL sync hota tha -> O(N) reindexes.
            # Ab lazy: writes par sirf dirty-flag; reindex next search pe ek baar.
            self.assertLessEqual(len(calls), 1)

    def test_semantic_search_still_correct_after_many_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            for i in range(15):
                store.remember(f"distributed redis lock pattern {i}", "print('lock')")
            store.remember("jwt authentication middleware setup", "print('auth')")
            hits = store.semantic_search("jwt auth token verification", top_k=3)
            self.assertTrue(hits)
            self.assertEqual(hits[0][0].goal, "jwt authentication middleware setup")

    def test_delete_removes_vector_incrementally(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            entry = store.remember("vector deletion probe goal", "print(2)")
            store.delete(entry.id)
            hits = store.semantic_search("vector deletion probe", top_k=5)
            self.assertEqual(hits, [])

    def test_recall_hit_does_not_trigger_vector_reindex(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.remember("recall hit persistence check", "print(3)")
            with patch.object(store.vector_store, "_reindex") as mock_reindex:
                hit = store.recall("recall hit persistence check")
                self.assertIsNotNone(hit)
                mock_reindex.assert_not_called()


class VectorStoreLazyIndexTests(unittest.TestCase):
    def test_lazy_dirty_flag_single_reindex(self):
        vs = VectorStore()
        calls = []
        original = vs._reindex
        with patch.object(vs, "_reindex", side_effect=lambda: (calls.append(1), original())):
            for i in range(10):
                vs.add_document(f"d{i}", f"document body {i}")
            self.assertEqual(calls, [])          # koi eager reindex nahi
            vs.search("document body")
            self.assertEqual(len(calls), 1)      # search pe ek hi baar
            vs.search("another query")
            self.assertEqual(len(calls), 1)      # ab clean -- dubara nahi

    def test_remove_document_marks_dirty(self):
        vs = VectorStore()
        vs.add_documents([("a", "alpha body", None), ("b", "beta body", None)])
        vs.search("alpha")
        self.assertTrue(vs.remove_document("b"))
        self.assertFalse(vs.remove_document("b"))  # already gone


class EnsureImagePreflightTests(unittest.TestCase):
    def test_returns_false_when_docker_unavailable(self):
        from saleha.core.execution_policy import ensure_image
        with patch("saleha.core.execution_policy.docker_available", return_value=False):
            ok, msg = ensure_image("python:3.12-slim")
        self.assertFalse(ok)

    def test_skips_pull_when_image_present(self):
        from saleha.core.execution_policy import ensure_image
        with patch("saleha.core.execution_policy.docker_available", return_value=True), \
             patch("saleha.core.execution_policy.image_present", return_value=True):
            ok, msg = ensure_image("python:3.12-slim")
        self.assertTrue(ok)
        self.assertIn("already present", msg)

    def test_auto_pull_disabled_env(self):
        from saleha.core.execution_policy import ensure_image
        env = {"SALEHA_DOCKER_AUTO_PULL": "0"}
        with patch("saleha.core.execution_policy.docker_available", return_value=True), \
             patch("saleha.core.execution_policy.image_present", return_value=False), \
             patch.dict(os.environ, env):
            ok, msg = ensure_image("python:3.12-slim")
        self.assertFalse(ok)
        self.assertIn("auto-pull disabled", msg)


if __name__ == "__main__":
    unittest.main()
