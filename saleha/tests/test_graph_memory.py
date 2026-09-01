"""Unit tests for Hierarchical Semantic Graph Memory."""

import unittest
import tempfile
import os
from saleha.core.graph_memory import HierarchicalGraphMemory, GraphNode, GraphEdge


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


if __name__ == "__main__":
    unittest.main()
