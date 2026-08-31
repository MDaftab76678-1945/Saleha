"""Unit tests for Multi-Repository & Monorepo Cross-Graph Swarm Indexer."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.multi_repo_graph import MultiRepoDependencyGraph


class MultiRepoGraphTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.graph = MultiRepoDependencyGraph()

        # Create two mock repos
        self.repo_a = os.path.join(self.temp_dir, "auth_service")
        os.makedirs(self.repo_a, exist_ok=True)
        with open(os.path.join(self.repo_a, "auth.py"), "w", encoding="utf-8") as f:
            f.write("class TokenManager:\n    def generate_token(self):\n        return 'jwt'\n")

        self.repo_b = os.path.join(self.temp_dir, "gateway_service")
        os.makedirs(self.repo_b, exist_ok=True)
        with open(os.path.join(self.repo_b, "gateway.py"), "w", encoding="utf-8") as f:
            f.write("def handle_request():\n    tm = TokenManager()\n    return tm.generate_token()\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_workspace_discovers_child_repos(self):
        meta = self.graph.scan_workspace(self.temp_dir)
        self.assertGreaterEqual(len(meta), 2)
        self.assertIn("auth_service", meta)
        self.assertIn("gateway_service", meta)

    def test_calculate_cross_repo_blast_radius(self):
        self.graph.scan_workspace(self.temp_dir)
        impacts = self.graph.calculate_cross_repo_blast_radius("TokenManager")
        self.assertGreaterEqual(len(impacts), 1)
        self.assertEqual(impacts[0].symbol_reference, "TokenManager")


if __name__ == "__main__":
    unittest.main()
