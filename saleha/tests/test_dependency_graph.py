"""Unit tests for Cross-File Dependency Graph and Atomic Multi-File Patcher."""

import os
import shutil
import tempfile
import unittest
from saleha.core.dependency_graph import CodebaseDependencyGraph


class DependencyGraphTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_dep_graph_")
        self.graph = CodebaseDependencyGraph(root_dir=self.temp_dir)

        # File A defines class Service and function helper()
        self.file_a = os.path.join(self.temp_dir, "service.py")
        with open(self.file_a, "w", encoding="utf-8") as f:
            f.write(
                "class Service:\n"
                "    def process(self):\n"
                "        return True\n\n"
                "def helper():\n"
                "    return 42\n"
            )

        # File B calls Service and helper
        self.file_b = os.path.join(self.temp_dir, "caller.py")
        with open(self.file_b, "w", encoding="utf-8") as f:
            f.write(
                "from service import Service, helper\n\n"
                "def run():\n"
                "    s = Service()\n"
                "    val = helper()\n"
                "    return s.process()\n"
            )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_graph_discovers_definitions(self):
        summary = self.graph.build_graph(root_dir=self.temp_dir)
        self.assertEqual(summary["total_files"], 2)
        self.assertIn("Service", self.graph.definitions)
        self.assertIn("helper", self.graph.definitions)

    def test_find_callers(self):
        self.graph.build_graph(root_dir=self.temp_dir)
        callers = self.graph.find_callers("helper")
        self.assertTrue(len(callers) >= 1)
        self.assertEqual(callers[0].caller_file, "caller.py")

    def test_atomic_multi_file_patch_success(self):
        patches = {
            self.file_a: "def helper():\n    return 100\n",
            self.file_b: "def run():\n    return 200\n"
        }
        res = self.graph.atomic_multi_file_patch(patches)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 2)

    def test_atomic_multi_file_patch_syntax_error_rolls_back(self):
        # Invalid syntax in one of the patches
        patches = {
            self.file_a: "def helper():\n    return 100\n",
            self.file_b: "def run( incomplete syntax"
        }
        res = self.graph.atomic_multi_file_patch(patches)
        self.assertFalse(res["success"])
        self.assertIn("Syntax validation failed", res["error"])


if __name__ == "__main__":
    unittest.main()

