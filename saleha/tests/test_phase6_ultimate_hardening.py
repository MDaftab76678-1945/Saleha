"""
Unit and integration tests for Phase 6: Multi-Attractor Energy Landscape, Pre-Warmed Sandbox Pool, and 2PC Multi-File Repair.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

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

    def test_atomic_2pc_multi_file_repair_success(self):
        header = self.root / "driver.h"
        caller1 = self.root / "main.c"
        caller2 = self.root / "worker.c"

        header.write_text("int* ptr = (int*)malloc(128);\n", encoding="utf-8")
        caller1.write_text("#include \"driver.h\"\nint rate = 1000 / 0;\n", encoding="utf-8")
        caller2.write_text("#include \"driver.h\"\nint divisor = 0;\n", encoding="utf-8")

        res = self.engine.repair_cross_module_violation(caller1, related_files=[header, caller2])
        assert res.success is True
        assert res.rolled_back is False
        assert res.total_files_affected >= 2
