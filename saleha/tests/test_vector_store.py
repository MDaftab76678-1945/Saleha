import unittest
from saleha.core.vector_store import VectorStore, SparseVectorEmbedder, cosine_similarity
from saleha.core.memory_store import MemoryStore


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = VectorStore()

    def test_sparse_vector_embedder_and_similarity(self):
        embedder = SparseVectorEmbedder()
        docs = [
            "Distributed rate limiting with Redis token bucket algorithm",
            "Relational database schema migration using SQLite and PostgreSQL",
            "Frontend user interface styling with Tailwind CSS and React"
        ]
        embedder.fit(docs)

        v1 = embedder.embed("Redis rate limiter tokens")
        v2 = embedder.embed("SQL database migration tables")
        v3 = embedder.embed("Redis distributed token bucket")

        # v1 and v3 should have high similarity
        sim_redis = cosine_similarity(v1, v3)
        sim_unrelated = cosine_similarity(v1, v2)

        self.assertGreater(sim_redis, 0.30)
        self.assertLess(sim_unrelated, sim_redis)

    def test_vector_store_top_k_search(self):
        self.store.add_document("doc1", "Build in-memory cache with LRU eviction policy")
        self.store.add_document("doc2", "Deploy microservices on Kubernetes cluster")
        self.store.add_document("doc3", "JWT authentication and RSA token validation")

        results = self.store.search("LRU cache memory", top_k=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].doc_id, "doc1")
        self.assertGreater(results[0].score, 0.2)

    def test_memory_store_semantic_search_integration(self):
        mem = MemoryStore(storage_path=":memory:")
        mem.remember("Design a distributed lock manager in Python", "def acquire_lock(): pass", tags=["redis", "lock"])
        mem.remember("Create HTML canvas charting library", "function draw() {}", tags=["frontend", "chart"])

        semantic_res = mem.semantic_search("distributed locking synchronization", top_k=1)
        self.assertEqual(len(semantic_res), 1)
        entry, score = semantic_res[0]
        self.assertIn("lock", entry.goal.lower())
        self.assertGreater(score, 0.1)


if __name__ == "__main__":
    unittest.main()
