"""
Unit and integration tests for Phase 5: Incremental AST Caching, Windows Job Sandbox, and Multi-File Auto-Repair.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from saleha.core.incremental_ast_cache import IncrementalASTCache
from saleha.core.windows_job_sandbox import WindowsJobSandbox
from saleha.core.multi_file_auto_repair import MultiFileAutoRepairEngine


class TestIncrementalASTCache:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, "test_cache.json")
        self.cache = IncrementalASTCache(cache_file_path=self.cache_file)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_miss_on_first_scan_and_hit_on_second(self):
        test_file = Path(self.temp_dir) / "sample.py"
        test_file.write_text("def valid_math(): return 10 + 20\n", encoding="utf-8")

        # 1. First scan: Cache Miss
        is_hit, entry = self.cache.audit_file_incremental(test_file)
        assert is_hit is False
        assert entry.passed is True

        # 2. Second scan without modification: Cache Hit
        is_hit2, entry2 = self.cache.audit_file_incremental(test_file)
        assert is_hit2 is True
        assert entry2.passed is True

    def test_directory_incremental_audit(self):
        # Create 5 files
        for i in range(5):
            fpath = Path(self.temp_dir) / f"mod_{i}.py"
            fpath.write_text(f"x = {i}\n", encoding="utf-8")

        res1 = self.cache.audit_directory_incremental(self.temp_dir)
        assert res1["total_files"] == 5
        assert res1["cache_misses"] == 5
        assert res1["cache_hits"] == 0

        # Second audit without changes should have 100% cache hits
        res2 = self.cache.audit_directory_incremental(self.temp_dir)
        assert res2["total_files"] == 5
        assert res2["cache_hits"] == 5
        assert res2["cache_misses"] == 0


class TestWindowsJobSandbox:
    def setup_method(self):
        self.sandbox = WindowsJobSandbox()

    def test_safe_execution_passes(self):
        code = "print('Hello Sandbox'); x = 40 + 2; print(f'Result: {x}')"
        res = self.sandbox.run_isolated_python_snippet(code, timeout_sec=2.0)
        assert res.passed is True
        assert "Result: 42" in res.output
        assert res.exit_code == 0

    def test_failing_snippet_caught_cleanly(self):
        code = "raise ValueError('Fatal Error in Test')"
        res = self.sandbox.run_isolated_python_snippet(code, timeout_sec=2.0)
        assert res.passed is False
        assert res.exit_code != 0
        assert "ValueError" in res.error

    def test_infinite_loop_timeout_isolation(self):
        code = "import time\nwhile True: time.sleep(0.1)"
        res = self.sandbox.run_isolated_python_snippet(code, timeout_sec=0.2)
        assert res.passed is False
        assert res.timed_out is True
        assert "CRITICAL_TIMEOUT" in res.error


class TestMultiFileAutoRepairEngine:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = MultiFileAutoRepairEngine(workspace_root=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multi_file_coordinated_repair(self):
        file1 = Path(self.temp_dir) / "module_a.py"
        file2 = Path(self.temp_dir) / "module_b.py"

        file1.write_text("divisor = 0\nres = 100 / divisor\n", encoding="utf-8")
        file2.write_text("divisor = 0\nres2 = 200 / divisor\n", encoding="utf-8")

        res = self.engine.repair_cross_module_violation(file1, related_files=[file2])
        assert res.success is True
        assert res.total_files_affected == 2

        # Verify both files are healed
        content1 = file1.read_text(encoding="utf-8")
        content2 = file2.read_text(encoding="utf-8")
        assert "divisor = 1" in content1
        assert "divisor = 1" in content2

