"""
Unit tests for Cross-File Dependency Graph, Cycle Detection, Topological Ordering,
and Atomic Multi-File Patcher.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from saleha.core.graph.dependency_graph import CodebaseDependencyGraph


class DependencyGraphTests(unittest.TestCase):
    def setUp(self) -> None:
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

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_graph_discovers_definitions(self) -> None:
        summary = self.graph.build_graph(root_dir=self.temp_dir)
        self.assertEqual(summary["total_files"], 2)
        self.assertIn("Service", self.graph.definitions)
        self.assertIn("helper", self.graph.definitions)
        # Class-scoped symbol check
        self.assertIn("Service.process", self.graph.definitions)

    def test_find_callers(self) -> None:
        self.graph.build_graph(root_dir=self.temp_dir)
        callers = self.graph.find_callers("helper")
        self.assertTrue(len(callers) >= 1)
        self.assertEqual(callers[0].caller_file, "caller.py")

    def test_atomic_multi_file_patch_success(self) -> None:
        patches = {
            self.file_a: "def helper():\n    return 100\n",
            self.file_b: "def run():\n    return 200\n",
        }
        res = self.graph.atomic_multi_file_patch(patches)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 2)

    def test_atomic_multi_file_patch_syntax_error_rolls_back(self) -> None:
        patches = {
            self.file_a: "def helper():\n    return 100\n",
            self.file_b: "def run( incomplete syntax",
        }
        res = self.graph.atomic_multi_file_patch(patches)
        self.assertFalse(res["success"])
        self.assertIn("Syntax validation failed", res["error"])

    def test_file_dependency_graph_and_topological_sort(self) -> None:
        self.graph.build_graph(root_dir=self.temp_dir)
        dep_graph = self.graph.get_file_dependency_graph()
        self.assertIn("caller.py", dep_graph)
        self.assertIn("service.py", dep_graph["caller.py"])

        order = self.graph.get_topological_order()
        self.assertIn("service.py", order)
        self.assertIn("caller.py", order)
        # service.py must precede caller.py in evaluation order
        self.assertTrue(order.index("service.py") < order.index("caller.py"))

    def test_detect_cycles_finds_circular_imports(self) -> None:
        # Create circular import: mod_x imports mod_y, mod_y imports mod_x
        mod_x = os.path.join(self.temp_dir, "mod_x.py")
        mod_y = os.path.join(self.temp_dir, "mod_y.py")
        with open(mod_x, "w", encoding="utf-8") as f:
            f.write("import mod_y\ndef x_func(): pass\n")
        with open(mod_y, "w", encoding="utf-8") as f:
            f.write("import mod_x\ndef y_func(): pass\n")

        self.graph.build_graph(root_dir=self.temp_dir)
        cycles = self.graph.detect_cycles()
        self.assertTrue(len(cycles) >= 1)
        found_cycle = any("mod_x.py" in c and "mod_y.py" in c for c in cycles)
        self.assertTrue(found_cycle)


if __name__ == "__main__":
    unittest.main()
