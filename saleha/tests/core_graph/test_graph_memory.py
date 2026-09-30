"""Unit tests for Hierarchical Semantic Graph Memory."""

import os
import subprocess
import sys
import tempfile
import unittest

from saleha.core.graph.graph_memory import HierarchicalGraphMemory


class TestHierarchicalGraphMemory(unittest.TestCase):
    """Test suite for HierarchicalGraphMemory knowledge graph and traversal."""

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        self.memory = HierarchicalGraphMemory(store_path=self.tmp_file)

    def tearDown(self):
        if os.path.exists(self.tmp_file):
            try:
                os.unlink(self.tmp_file)
            except OSError:
                pass

    def test_add_node_and_edge(self):
        n1 = self.memory.add_node("task_1", "Build Auth API", "task")
        n2 = self.memory.add_node("mod_1", "auth.py", "module")
        edge = self.memory.add_edge("task_1", "mod_1", "CONTAINS")

        self.assertIn("task_1", self.memory.nodes)
        self.assertIn("mod_1", self.memory.nodes)
        self.assertEqual(len(self.memory.edges), 1)
        self.assertEqual(edge.relation, "CONTAINS")

    def test_record_solution_hierarchy_and_query_subgraph(self):
        self.memory.record_solution_hierarchy(
            goal="User Authentication Service",
            module_name="auth_service.py",
            functions=[
                {"name": "login", "signature": "def login(username, password)"},
                {"name": "register", "signature": "def register(username, email, password)"},
            ],
            tests=["test_login_success", "test_register_duplicate"],
        )

        task_node = next(n for n in self.memory.nodes.values() if n.node_type == "task")
        subgraph = self.memory.query_subgraph(task_node.node_id, max_depth=2)

        self.assertTrue(len(subgraph["nodes"]) >= 3)
        self.assertTrue(len(subgraph["edges"]) >= 2)

    def test_export_mermaid_format(self):
        self.memory.add_node("a", "Node A", "task")
        self.memory.add_node("b", "Node B", "module")
        self.memory.add_edge("a", "b", "CONTAINS")

        mermaid = self.memory.export_mermaid()
        self.assertIn("graph TD", mermaid)
        self.assertIn("a -->|CONTAINS| b", mermaid)


class TestGraphMemoryDurability(unittest.TestCase):
    """Memory must survive a restart and must never be silently lost."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = os.path.join(self._td.name, "graph_memory.json")

    def tearDown(self) -> None:
        self._td.cleanup()

    def _record(self, memory: HierarchicalGraphMemory) -> None:
        memory.record_solution_hierarchy(
            goal="Auth service", module_name="auth.py",
            functions=[{"name": "login"}], tests=["test_login"])

    def test_ids_are_stable_across_processes(self) -> None:
        """hash() is salted per process; a stable id must not be."""
        code = ("from saleha.core.graph.graph_memory import HierarchicalGraphMemory as H;"
                "print(H.stable_id('task', 'Auth service'))")
        outs = set()
        for seed in ("1", "2", "3"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONIOENCODING="utf-8")
            res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                 text=True, encoding="utf-8", env=env, timeout=60)
            self.assertEqual(res.returncode, 0, res.stderr)
            outs.add(res.stdout.strip())
        self.assertEqual(len(outs), 1, outs)

    def test_recording_twice_does_not_duplicate(self) -> None:
        memory = HierarchicalGraphMemory(store_path=self.store)
        self._record(memory)
        nodes, edges = len(memory.nodes), len(memory.edges)
        self._record(memory)
        self.assertEqual((len(memory.nodes), len(memory.edges)), (nodes, edges))

    def test_memory_is_found_again_after_restart(self) -> None:
        self._record(HierarchicalGraphMemory(store_path=self.store))
        again = HierarchicalGraphMemory(store_path=self.store)
        self.assertTrue(any(n.label == "Auth service" for n in again.nodes.values()))
        before = (len(again.nodes), len(again.edges))
        self._record(again)   # same solution recorded by the "next run"
        self.assertEqual((len(again.nodes), len(again.edges)), before)

    def test_same_function_name_in_two_modules_stays_distinct(self) -> None:
        memory = HierarchicalGraphMemory(store_path=self.store)
        memory.record_solution_hierarchy("g1", "a.py", [{"name": "run"}], [])
        memory.record_solution_hierarchy("g2", "b.py", [{"name": "run"}], [])
        self.assertEqual(sum(1 for n in memory.nodes.values() if n.node_type == "function"), 2)

    def test_unreadable_store_is_moved_aside_not_overwritten(self) -> None:
        with open(self.store, "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        memory = HierarchicalGraphMemory(store_path=self.store)
        self.assertIn("JSONDecodeError", memory.load_error)
        self.assertTrue(memory.quarantined_to)
        with open(memory.quarantined_to, encoding="utf-8") as f:
            self.assertEqual(f.read(), "{ this is not json")   # original bytes kept
        self._record(memory)   # saving now must not destroy the old file
        self.assertTrue(os.path.exists(memory.quarantined_to))

    def test_empty_store_is_not_treated_as_corruption(self) -> None:
        open(self.store, "w").close()
        memory = HierarchicalGraphMemory(store_path=self.store)
        self.assertEqual(memory.load_error, "")
        self.assertEqual(memory.quarantined_to, "")

    def test_save_failure_is_raised_not_swallowed(self) -> None:
        blocker = os.path.join(self._td.name, "blocker")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("a file, so it cannot be a directory")
        memory = HierarchicalGraphMemory(store_path=os.path.join(blocker, "graph_memory.json"))
        with self.assertRaises(OSError):
            self._record(memory)


if __name__ == "__main__":
    unittest.main()
