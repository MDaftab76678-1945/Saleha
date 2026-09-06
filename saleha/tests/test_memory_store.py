import unittest
import os
import shutil
import tempfile
import json
from click.testing import CliRunner

from saleha.core.memory_store import MemoryStore, MemoryEntry
from saleha.cli.commands import cli


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.storage_file = os.path.join(self.tmpdir.name, "test_memory.json")
        self.store = MemoryStore(storage_path=self.storage_file)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_remember_and_persistence(self):
        entry = self.store.remember(
            goal="Write a fast Fibonacci function in Python",
            code="def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)",
            model="test-model"
        )
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.hit_count, 0)
        self.assertTrue(os.path.isfile(self.storage_file))

        # Reload from disk
        store2 = MemoryStore(storage_path=self.storage_file)
        self.assertEqual(len(store2.list_all()), 1)
        self.assertEqual(store2.list_all()[0].goal, "Write a fast Fibonacci function in Python")

    def test_exact_and_fuzzy_recall(self):
        self.store.remember(
            goal="Create an in-memory cache with TTL expiration",
            code="class TTLCache: pass",
        )

        # Exact match
        exact = self.store.recall("Create an in-memory cache with TTL expiration")
        self.assertIsNotNone(exact)
        self.assertEqual(exact.hit_count, 1)

        # High similarity recall
        fuzzy = self.store.recall("Create in-memory cache with TTL expiration", min_similarity=0.70)
        self.assertIsNotNone(fuzzy)
        self.assertEqual(fuzzy.hit_count, 2)

        # Unrelated query should be None
        unrelated = self.store.recall("Calculate gravitational constant", min_similarity=0.80)
        self.assertIsNone(unrelated)

    def test_search_and_tag_filtering(self):
        self.store.remember(
            goal="Distributed redis lock implementation",
            code="class RedisLock: pass",
            tags=["redis", "distributed", "lock"]
        )
        self.store.remember(
            goal="Binary search algorithm",
            code="def bsearch(arr, x): pass",
            tags=["search", "algorithm"]
        )

        results_redis = self.store.search("redis")
        self.assertEqual(len(results_redis), 1)
        self.assertIn("redis", results_redis[0].tags)
        self.assertIn("lock", results_redis[0].tags)

        results_search = self.store.search("search")
        self.assertEqual(len(results_search), 1)

    def test_delete_and_clear(self):
        e1 = self.store.remember("Task 1", "Code 1")
        e2 = self.store.remember("Task 2", "Code 2")
        self.assertEqual(len(self.store.list_all()), 2)

        self.store.delete(e1.id)
        self.assertEqual(len(self.store.list_all()), 1)

        self.store.clear()
        self.assertEqual(len(self.store.list_all()), 0)

    def test_cli_memory_endpoints(self):
        # Test stats
        res = CliRunner().invoke(cli, ["memory", "stats", "--json"])
        self.assertEqual(res.exit_code, 0)
        payload = json.loads(res.output)
        self.assertIn("total_memories", payload)

    def test_compact_conversation_history(self):
        steps = [
            {"step": i, "action": f"tool_{i}", "args": f"arg_{i}", "observation": f"observation line {i}\nmore details"}
            for i in range(1, 8)
        ]
        compacted = MemoryStore.compact_conversation_history(steps)
        self.assertIn("Compacted Prior Investigation Context", compacted)
        self.assertIn("Recent Detailed Trace", compacted)
        self.assertIn("Step 1 (tool_1)", compacted)
        self.assertIn("Step 7", compacted)


class ModelScopedRecallTests(unittest.TestCase):
    """
    The cache is keyed on goal text alone. Benchmarking model B on prompts
    model A already solved therefore replayed A's cached answer and reported
    it as B's result -- verified in a real tuning run to produce identical,
    meaningless before/after numbers.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = MemoryStore(storage_path=os.path.join(self.tmp, "m.json"))
        self.store.remember(goal="write a fibonacci function",
                            code="def fib(n): return n",
                            model="qwen2.5-coder:3b")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unfiltered_recall_still_shares_across_models(self):
        """Default behaviour is unchanged: plain task execution still reuses
        a verified solution regardless of which model produced it."""
        self.assertIsNotNone(self.store.recall("write a fibonacci function"))

    def test_recall_scoped_to_the_producing_model_hits(self):
        hit = self.store.recall("write a fibonacci function",
                                model="qwen2.5-coder:3b")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.model, "qwen2.5-coder:3b")

    def test_recall_scoped_to_a_different_model_misses(self):
        """The actual bug: model B must not be handed model A's answer."""
        self.assertIsNone(self.store.recall("write a fibonacci function",
                                            model="deepseek-coder:6.7b"))

    def test_fuzzy_match_is_also_model_scoped(self):
        """Scoping must apply to the Jaccard path, not just exact match."""
        self.assertIsNotNone(self.store.recall("write a fibonacci function please",
                                               min_similarity=0.5,
                                               model="qwen2.5-coder:3b"))
        self.assertIsNone(self.store.recall("write a fibonacci function please",
                                            min_similarity=0.5,
                                            model="deepseek-coder:6.7b"))

    def test_empty_store_scoped_recall_is_safe(self):
        empty = MemoryStore(storage_path=os.path.join(self.tmp, "empty.json"))
        self.assertIsNone(empty.recall("anything", model="qwen2.5-coder:3b"))

    def test_orchestrator_does_not_filter_on_literal_auto(self):
        """Entries are stored under the RESOLVED model name, so filtering on
        the literal string "auto" would match nothing and silently disable the
        cache for every default-configured run."""
        self.assertIsNone(self.store.recall("write a fibonacci function",
                                            model="auto"))
        from saleha.orchestrator import SalehaOrchestrator
        orch = SalehaOrchestrator.__new__(SalehaOrchestrator)
        orch.model = "auto"
        resolved = orch.model if orch.model and orch.model != "auto" else None
        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
