import unittest
import os
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


if __name__ == "__main__":
    unittest.main()
