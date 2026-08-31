"""Unit tests for Live Interactive Architecture Graph Visualizer."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.graph_visualizer import ArchitectureGraphVisualizer


class GraphVisualizerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.visualizer = ArchitectureGraphVisualizer(root_dir=self.temp_dir)

        # Create a sample python file in temp_dir
        with open(os.path.join(self.temp_dir, "sample.py"), "w", encoding="utf-8") as f:
            f.write("class UserService:\n    def get_user(self):\n        return 'alice'\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_graph_data(self):
        data = self.visualizer.generate_graph_data()
        self.assertIn("nodes", data)
        self.assertIn("links", data)
        self.assertGreaterEqual(len(data["nodes"]), 1)

    def test_render_html_creates_standalone_file(self):
        out_file = os.path.join(self.temp_dir, "test_graph.html")
        rendered = self.visualizer.render_html(output_path=out_file)
        self.assertTrue(os.path.isfile(rendered))
        with open(rendered, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("Saleha Architecture Graph", content)
        self.assertIn("d3.forceSimulation", content)


if __name__ == "__main__":
    unittest.main()

