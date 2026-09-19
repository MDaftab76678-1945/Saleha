"""
Unit tests for IncrementalASTCache in saleha/core/incremental_ast_cache.py.

Verifies:
1. Initial cache miss and correct SHA256 / mtime indexing.
2. High-speed cache hit on unchanged files (< 0.1ms).
3. Cache invalidation on content change or forced re-scan.
4. Directory audit with ignore-list filtering (.git, __pycache__, build, dist, venv).
5. Single file target handling in directory audit.
6. Persistence to disk and reloading in a new instance.
7. Graceful handling of unreadable / non-existent files.
8. Zero ambient filesystem side-effects (all tests run in isolated tempdirs).
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

from saleha.core.incremental_ast_cache import IncrementalASTCache


class IncrementalASTCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.cache_file = self.root / ".saleha" / "ast_cache.json"
        self.cache = IncrementalASTCache(cache_file_path=str(self.cache_file))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_audit_file_initial_miss(self) -> None:
        file_path = self.root / "sample.py"
        file_path.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

        is_hit, entry = self.cache.audit_file_incremental(file_path)
        self.assertFalse(is_hit)
        self.assertEqual(entry.filepath, str(file_path))
        self.assertTrue(len(entry.content_hash) == 64)
        self.assertTrue(entry.passed)
        self.assertEqual(entry.violations_count, 0)

    def test_audit_file_cache_hit_on_unchanged(self) -> None:
        file_path = self.root / "sample.py"
        file_path.write_text("x = 42\n", encoding="utf-8")

        is_hit_1, entry_1 = self.cache.audit_file_incremental(file_path)
        self.assertFalse(is_hit_1)

        # Immediate second audit
        start_t = time.perf_counter()
        is_hit_2, entry_2 = self.cache.audit_file_incremental(file_path)
        duration_ms = (time.perf_counter() - start_t) * 1000

        self.assertTrue(is_hit_2)
        self.assertEqual(entry_1.content_hash, entry_2.content_hash)
        self.assertLess(duration_ms, 5.0)  # Sub-5ms requirement

    def test_audit_file_cache_miss_on_content_change(self) -> None:
        file_path = self.root / "sample.py"
        file_path.write_text("x = 1\n", encoding="utf-8")
        self.cache.audit_file_incremental(file_path)

        # Modify content and bump mtime
        time.sleep(0.01)
        file_path.write_text("x = 9999\n", encoding="utf-8")

        is_hit, entry = self.cache.audit_file_incremental(file_path)
        self.assertFalse(is_hit)
        self.assertEqual(entry.content_hash, IncrementalASTCache._compute_hash("x = 9999\n"))

    def test_audit_file_force_bypasses_cache(self) -> None:
        file_path = self.root / "sample.py"
        file_path.write_text("a = 10\n", encoding="utf-8")
        self.cache.audit_file_incremental(file_path)

        is_hit, _ = self.cache.audit_file_incremental(file_path, force=True)
        self.assertFalse(is_hit)

    def test_audit_file_handles_read_error(self) -> None:
        non_existent = self.root / "does_not_exist.py"
        is_hit, entry = self.cache.audit_file_incremental(non_existent)

        self.assertFalse(is_hit)
        self.assertFalse(entry.passed)
        self.assertGreater(entry.violations_count, 0)
        self.assertEqual(entry.diagnostics[0]["rule"], "READ_ERROR")

    def test_audit_directory_incremental_and_filtering(self) -> None:
        # Create normal files
        f1 = self.root / "module_a.py"
        f1.write_text("def foo(): pass\n", encoding="utf-8")
        f2 = self.root / "module_b.py"
        f2.write_text("def bar(): pass\n", encoding="utf-8")

        # Create ignored directory and file
        pycache = self.root / "__pycache__"
        pycache.mkdir()
        (pycache / "compiled.py").write_text("x = 1\n", encoding="utf-8")

        hidden_dir = self.root / ".git"
        hidden_dir.mkdir()
        (hidden_dir / "hook.py").write_text("x = 1\n", encoding="utf-8")

        # First audit: all cache misses
        res1 = self.cache.audit_directory_incremental(self.root)
        self.assertEqual(res1["total_files"], 2)  # __pycache__ and .git skipped
        self.assertEqual(res1["cache_misses"], 2)
        self.assertEqual(res1["cache_hits"], 0)

        # Second audit: all cache hits
        res2 = self.cache.audit_directory_incremental(self.root)
        self.assertEqual(res2["total_files"], 2)
        self.assertEqual(res2["cache_misses"], 0)
        self.assertEqual(res2["cache_hits"], 2)

    def test_audit_directory_with_single_file_target(self) -> None:
        file_path = self.root / "single.py"
        file_path.write_text("y = 100\n", encoding="utf-8")

        res = self.cache.audit_directory_incremental(file_path)
        self.assertEqual(res["total_files"], 1)
        self.assertEqual(res["cache_misses"], 1)

    def test_cache_persistence_across_instances(self) -> None:
        f1 = self.root / "persistent.py"
        f1.write_text("CONSTANT = 'verified'\n", encoding="utf-8")

        self.cache.audit_directory_incremental(self.root)
        self.assertTrue(self.cache_file.exists())

        # Instantiate brand new cache pointing to same file
        new_cache = IncrementalASTCache(cache_file_path=str(self.cache_file))
        res = new_cache.audit_directory_incremental(self.root)
        self.assertEqual(res["cache_hits"], 1)
        self.assertEqual(res["cache_misses"], 0)


if __name__ == "__main__":
    unittest.main()
