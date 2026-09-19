"""Unit and Integration Tests for HypergraphIndexer.

Validates multi-file AST symbol hypergraph traversal, class/method scoping,
base class inheritance resolution, and bidirectional caller edge linking.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import Optional

from saleha.core.hypergraph_indexer import (
    HypergraphIndexer,
    HypergraphIndexStats,
    SymbolNode,
)


class TestHypergraphIndexer(unittest.TestCase):
    """Test suite for HypergraphIndexer semantic symbol traversal."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_file(self, rel_path: str, content: str) -> str:
        full_path = os.path.join(self.tmp_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    def test_scoped_class_and_method_indexing(self) -> None:
        code = '''
class Greeter:
    """Greeter class docstring."""
    def __init__(self, prefix: str = "Hello") -> None:
        self.prefix = prefix

    def greet(self, name: str) -> str:
        """Return formatted greeting."""
        return f"{self.prefix}, {name}"

def standalone_func(x: int) -> int:
    return x * 2
'''
        self._write_file("greeting.py", code)
        indexer = HypergraphIndexer(root_dir=self.tmp_dir)
        stats: HypergraphIndexStats = indexer.scan_directory(self.tmp_dir)

        self.assertEqual(stats.total_files_scanned, 1)
        self.assertGreaterEqual(stats.total_symbols_indexed, 3)

        # Check Class symbol
        class_ctx = indexer.get_symbol_context("Greeter")
        self.assertIsNotNone(class_ctx)
        self.assertEqual(class_ctx["type"], "class")
        self.assertIn("Greeter class docstring.", class_ctx["docstring"])

        # Check Scoped Method symbol
        method_ctx = indexer.get_symbol_context("Greeter.greet")
        self.assertIsNotNone(method_ctx)
        self.assertEqual(method_ctx["type"], "method")
        self.assertIn("name", method_ctx["parameters"])

        # Check Standalone Function
        func_ctx = indexer.get_symbol_context("standalone_func")
        self.assertIsNotNone(func_ctx)
        self.assertEqual(func_ctx["type"], "function")

    def test_inheritance_simple_and_attribute(self) -> None:
        code = '''
import unittest

class BaseWorker:
    def execute(self) -> None:
        pass

class CustomWorker(BaseWorker):
    def execute(self) -> None:
        super().execute()

class WorkerTest(unittest.TestCase):
    def test_run(self) -> None:
        pass
'''
        self._write_file("worker.py", code)
        indexer = HypergraphIndexer(root_dir=self.tmp_dir)
        indexer.scan_directory(self.tmp_dir)

        custom_ctx = indexer.get_symbol_context("CustomWorker")
        self.assertIsNotNone(custom_ctx)
        self.assertIn("BaseWorker", custom_ctx["dependencies"])

        test_ctx = indexer.get_symbol_context("WorkerTest")
        self.assertIsNotNone(test_ctx)
        self.assertIn("unittest.TestCase", test_ctx["dependencies"])

    def test_cross_symbol_caller_linking(self) -> None:
        file_a = '''
def helper_utility(val: int) -> int:
    return val + 42
'''
        file_b = '''
from file_a import helper_utility

def business_logic(num: int) -> int:
    return helper_utility(num)
'''
        self._write_file("file_a.py", file_a)
        self._write_file("file_b.py", file_b)

        indexer = HypergraphIndexer(root_dir=self.tmp_dir)
        indexer.scan_directory(self.tmp_dir)

        helper_ctx = indexer.get_symbol_context("helper_utility")
        self.assertIsNotNone(helper_ctx)
        # business_logic calls helper_utility, so it must be listed as caller
        self.assertIn("business_logic", helper_ctx["callers"])

    def test_find_impacted_files(self) -> None:
        file_a = '''
class StorageEngine:
    def save(self, data: str) -> bool:
        return True
'''
        file_b = '''
from file_a import StorageEngine

class AppService:
    def __init__(self) -> None:
        self.storage = StorageEngine()

    def process(self, item: str) -> bool:
        return self.storage.save(item)
'''
        self._write_file("service/file_a.py", file_a)
        self._write_file("service/file_b.py", file_b)

        indexer = HypergraphIndexer(root_dir=self.tmp_dir)
        indexer.scan_directory(self.tmp_dir)

        impacted = indexer.find_impacted_files("StorageEngine")
        rel_b = "service/file_b.py"
        self.assertIn(rel_b, impacted)

    def test_empty_and_broken_syntax_resilience(self) -> None:
        self._write_file("empty.py", "")
        self._write_file("broken.py", "def broken_syntax(:\n    pass\n")

        indexer = HypergraphIndexer(root_dir=self.tmp_dir)
        stats = indexer.scan_directory(self.tmp_dir)
        self.assertEqual(stats.total_files_scanned, 2)
        self.assertEqual(stats.total_symbols_indexed, 0)
        self.assertIsNone(indexer.get_symbol_context("nonexistent"))


if __name__ == "__main__":
    unittest.main()
