"""
Unit and integration tests for Phase 6: Multi-Attractor Energy Landscape, Pre-Warmed Sandbox Pool, and 2PC Multi-File Repair.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

from saleha.core.hyperbolic_engine import (
    HyperbolicVector,
    MultiAttractorLandscape,
    SAMHAttractorController,
    HYPERBOLIC_DIM,
)
from saleha.core.prewarmed_sandbox_pool import PreWarmedSandboxPool
from saleha.core.multi_file_auto_repair import (
    MultiFileAutoRepairEngine,
    BiDirectionalDependencyGraph,
)


class TestMultiAttractorLandscape:
    def setup_method(self):
        self.landscape = MultiAttractorLandscape()

    def test_all_10_department_attractors_present(self):
        assert len(self.landscape.DEPARTMENT_ATTRACTORS) == 10
        assert "SYSTEMS_KERNEL" in self.landscape.DEPARTMENT_ATTRACTORS
        assert "SECURITY_GOVERNANCE" in self.landscape.DEPARTMENT_ATTRACTORS
        assert "QUANTUM_PHYSICS" in self.landscape.DEPARTMENT_ATTRACTORS

    def test_lorentz_coordinate_conversion(self):
        v = HyperbolicVector([0.2] * HYPERBOLIC_DIM)
        x_0, spatial = v.to_lorentz_coordinates()
        assert x_0 > 1.0  # Time-like component > 1 in hyperboloid
        assert len(spatial) == HYPERBOLIC_DIM

    def test_energy_minimization_picks_nearest_basin(self):
        # Create a vector close to SECURITY_GOVERNANCE attractor
        sec_attr = self.landscape.DEPARTMENT_ATTRACTORS["SECURITY_GOVERNANCE"]
        noisy_vec = sec_attr.mobius_addition(HyperbolicVector([0.05] * HYPERBOLIC_DIM))

        dept, attr, dist = self.landscape.find_nearest_attractor(noisy_vec)
        assert dept == "SECURITY_GOVERNANCE"
        assert dist < 1.0

    def test_multi_attractor_healing(self):
        drifted = HyperbolicVector([0.35] * HYPERBOLIC_DIM)
        healed, was_healed, dept, dist = self.landscape.apply_multi_attractor_healing(drifted)
        assert was_healed is True
        target_attr = self.landscape.DEPARTMENT_ATTRACTORS[dept]
        orig_dist = drifted.hyperbolic_distance(target_attr)
        assert dist < orig_dist


class TestPreWarmedSandboxPool:
    def setup_method(self):
        self.pool = PreWarmedSandboxPool(pool_size=4)

    def test_prewarmed_fast_execution(self):
        code = "a = 10; b = 20; res = a + b"
        res = self.pool.run_fast_sandboxed_snippet(code)
        assert res.passed is True
        assert res.is_warm is True
        assert res.exit_code == 0
        assert res.execution_time_us < 50000.0  # Fast sub-50ms sandboxed execution

    def test_failing_snippet_isolated_cleanly(self):
        code = "100 / 0"
        res = self.pool.run_fast_sandboxed_snippet(code)
        assert res.passed is False
        assert res.exit_code == 1
        assert "division by zero" in res.error.lower()


class TestMultiFileTwoPhaseCommit:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)
        self.engine = MultiFileAutoRepairEngine(workspace_root=self.root)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bidirectional_dependency_graph_building(self):
        file_a = self.root / "module_a.py"
        file_b = self.root / "module_b.py"
        
        file_a.write_text("import module_b\n", encoding="utf-8")
        file_b.write_text("x = 10\n", encoding="utf-8")

        graph = BiDirectionalDependencyGraph(self.root)
        blast = graph.get_blast_radius("module_b.py")
        assert "module_a.py" in blast

    def test_c_division_is_declined_not_regex_replaced(self):
        """
        This test previously asserted `success is True` for a batch of C files
        whose only "repair" was a regex turning `/ 0` into `/ 1` across the
        whole file, string literals included. There is no C parser here, so
        the division case is now declined and reported rather than guessed at.
        """
        header = self.root / "driver.h"
        caller1 = self.root / "main.c"

        header.write_text("int* ptr = (int*)malloc(128);\n", encoding="utf-8")
        caller1.write_text('#include "driver.h"\nint rate = 1000 / 0;\n',
                           encoding="utf-8")

        res = self.engine.repair_cross_module_violation(
            caller1, related_files=[header])

        assert res.success is False
        assert res.total_files_affected == 0
        assert any("not patched" in d for d in res.declined)
        # The file is untouched: no regex ran over it.
        assert "1000 / 0" in caller1.read_text(encoding="utf-8")

    def test_string_literals_are_never_rewritten(self):
        """
        The old regex rewrote `URL = "http://a/b/ 0k"` to `".../ 1k"`. The
        patcher is AST-based now, so only code moves.
        """
        f = self.root / "urls.py"
        f.write_text('RATE = 0\nURL = "http://a/b/ 0k"\ntotal = 100 / RATE\n',
                     encoding="utf-8")

        self.engine.repair_cross_module_violation(f)
        after = f.read_text(encoding="utf-8")

        assert 'URL = "http://a/b/ 0k"' in after
        assert "RATE = 1" in after

    def test_a_guard_is_not_rewritten_into_dead_code(self):
        """
        Given a guarded zero constant the old code raised it to 1, turning the
        guard into dead code and changing the program's result from 0 to
        100.0 -- and reported success. It must decline instead.
        """
        f = self.root / "guarded.py"
        source = ("divisor = 0\n"
                  "if divisor == 0:\n"
                  "    result = 0\n"
                  "else:\n"
                  "    result = 100 / divisor\n")
        f.write_text(source, encoding="utf-8")

        res = self.engine.repair_cross_module_violation(f)

        assert f.read_text(encoding="utf-8") == source
        assert res.total_files_affected == 0
        assert any("guard" in d for d in res.declined)

        namespace = {}
        exec(f.read_text(encoding="utf-8"), namespace)
        assert namespace["result"] == 0

    def test_unguarded_constant_is_patched(self):
        """The case the module genuinely can fix."""
        f = self.root / "rate.py"
        f.write_text("RATE = 0\ntotal = 100 / RATE\n", encoding="utf-8")

        res = self.engine.repair_cross_module_violation(f)

        assert res.success is True
        assert res.total_files_affected == 1
        assert res.rolled_back is False
        assert "RATE = 1" in f.read_text(encoding="utf-8")

    def test_a_failed_write_restores_every_file_already_written(self):
        """
        The atomicity claim, tested. Previously Phase 2 was a bare loop: the
        first file stayed modified on disk, the second did not, and the
        exception escaped the call. Nothing in either test file ever failed a
        write, which is why the claim survived for as long as it did.
        """
        a = self.root / "a.py"
        b = self.root / "b.py"
        original = "divisor = 0\nres = 100 / divisor\n"
        a.write_text(original, encoding="utf-8")
        b.write_text(original, encoding="utf-8")

        real_write = Path.write_text
        calls = {"n": 0}

        def failing_write(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated disk full")
            return real_write(self, *args, **kwargs)

        engine = MultiFileAutoRepairEngine(workspace_root=self.root)
        with patch.object(Path, "write_text", failing_write):
            res = engine.repair_cross_module_violation(a, related_files=[b])

        assert res.success is False
        assert res.rolled_back is True
        assert res.rollback_failed is False
        # Both files back to their original bytes: no partial state.
        assert a.read_text(encoding="utf-8") == original
        assert b.read_text(encoding="utf-8") == original

    def test_rolled_back_is_false_when_nothing_was_written(self):
        """
        The old code returned `rolled_back=True` from the abort branch, which
        runs before any write -- claiming an undo of something that never
        happened.
        """
        f = self.root / "clean.py"
        f.write_text("x = 1\n", encoding="utf-8")

        res = self.engine.repair_cross_module_violation(f)

        assert res.rolled_back is False
        assert res.rollback_failed is False

    def test_declined_findings_are_not_reported_as_a_clean_scan(self):
        """
        "Nothing to fix" and "found defects I cannot fix" are different
        claims. Reporting the second as the first is the reassuring default
        this module was audited for.
        """
        f = self.root / "literal.py"
        f.write_text("x = 5 / 0\n", encoding="utf-8")

        res = self.engine.repair_cross_module_violation(f)

        assert res.success is False
        assert res.declined
        assert "not a clean bill of health" in res.message

    def test_ambiguous_basenames_are_declined_not_patched_blindly(self):
        """
        The graph keys on basename, so `pkg1/utils.py` and `pkg2/utils.py`
        are one node. The old code resolved that with `rglob` and patched
        both. It must decline instead.
        """
        (self.root / "pkg1").mkdir()
        (self.root / "pkg2").mkdir()
        (self.root / "pkg1" / "utils.py").write_text("A = 1\n", encoding="utf-8")
        (self.root / "pkg2" / "utils.py").write_text("B = 2\n", encoding="utf-8")
        main = self.root / "main.py"
        main.write_text("import utils\n", encoding="utf-8")

        graph = BiDirectionalDependencyGraph(self.root)
        assert graph.is_ambiguous("utils.py")

    def test_imports_inside_functions_are_found(self):
        """
        The old indexer used `line.startswith("import ")`, so any indented
        import -- inside a function, a `try:` block, a conditional -- was
        invisible.
        """
        (self.root / "helper.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "lazy.py").write_text(
            "def load():\n    import helper\n    return helper\n",
            encoding="utf-8")

        graph = BiDirectionalDependencyGraph(self.root)
        assert "lazy.py" in graph.get_blast_radius("helper.py")

    def test_the_old_fabricated_message_is_gone(self):
        """`2PC Atomic Commit` claimed a property the code did not have."""
        import saleha.core.multi_file_auto_repair as module
        source = Path(module.__file__).read_text(encoding="utf-8")
        code_lines = [ln for ln in source.splitlines()
                      if "2PC Atomic Commit:" in ln and "Successfully healed" in ln]
        assert code_lines == []
