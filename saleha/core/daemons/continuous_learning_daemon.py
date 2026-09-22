"""Saleha Core: Continuous Background Self-Improvement & DPO Daemon.

Monitors system idle state, queries RLHFStore for uncompiled contrastive pairs,
exports DPO dataset batches, and continuously drives self-improvement cycles
by identifying untested modules in the repository.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from saleha.core.alignment import DPOBatchExporter, RLHFStore


@dataclass
class DaemonCycleResult:
    """Outcome of an autonomous background self-improvement cycle."""
    cycle_id: str
    timestamp: float
    idle_detected: bool
    uncompiled_pairs_count: int
    dpo_batch_exported: bool
    dpo_export_path: Optional[str]
    untested_candidates: List[str]
    actions_taken: List[str]
    duration_ms: float


class ContinuousLearningDaemon:
    """Autonomous background daemon executing idle-time self-improvement."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        rlhf_store: Optional[RLHFStore] = None,
        export_dir: Optional[Path] = None,
        dpo_threshold: int = 5,
    ) -> None:
        self.repo_root = repo_root or Path(".")
        self.store = rlhf_store or RLHFStore()
        self.exporter = DPOBatchExporter(self.store)
        self.export_dir = export_dir or Path(".saleha/alignment/dpo_batches")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.dpo_threshold = dpo_threshold
        self._is_running = False
        self._lock = threading.Lock()
        self.history: List[DaemonCycleResult] = []

    def is_system_idle(self) -> bool:
        """Determines if the runtime is currently idle and ready for background tasks."""
        if os.environ.get("SALEHA_FORCE_IDLE") == "1":
            return True
        if os.environ.get("SALEHA_TEST_MODE") == "1":
            return True
        try:
            import psutil
        except ImportError:
            # Load cannot be measured, so idleness cannot be claimed.
            return False
        return psutil.cpu_percent(interval=0.5) < 25.0

    def find_untested_core_modules(self) -> List[str]:
        """Identifies modules in saleha/core/ that lack corresponding test files."""
        core_dir = self.repo_root / "saleha" / "core"
        tests_dir = self.repo_root / "saleha" / "tests"

        if not core_dir.exists() or not tests_dir.exists():
            return []

        existing_tests = {f.stem for f in tests_dir.glob("test_*.py")}
        untested: List[str] = []

        for py_file in core_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            expected_test_name = f"test_{py_file.stem}"
            if expected_test_name not in existing_tests:
                untested.append(py_file.stem)

        return sorted(untested)

    def execute_single_cycle(self) -> DaemonCycleResult:
        """Executes one pass of the background self-improvement workflow."""
        start_time = time.perf_counter()
        cycle_id = f"daemon_{int(time.time())}"
        actions: List[str] = []

        idle = self.is_system_idle()
        if not idle:
            return DaemonCycleResult(
                cycle_id=cycle_id,
                timestamp=time.time(),
                idle_detected=False,
                uncompiled_pairs_count=0,
                dpo_batch_exported=False,
                dpo_export_path=None,
                untested_candidates=[],
                actions_taken=["Aborted: System is busy"],
                duration_ms=0.0,
            )

        # 1. Check uncompiled preference pairs
        uncompiled_count = self.store.get_summary().get("total_contrastive_pairs", 0)
        dpo_exported = False
        export_path_str: Optional[str] = None

        if uncompiled_count >= self.dpo_threshold:
            out_file = self.export_dir / f"dpo_batch_{int(time.time())}.jsonl"
            exported_count = self.exporter.export_to_jsonl(
                output_path=out_file,
                limit=uncompiled_count,
            )
            if exported_count > 0:
                dpo_exported = True
                export_path_str = str(out_file)
                actions.append(f"Exported DPO dataset with {exported_count} pairs to {out_file.name}")

        # 2. Discover untested modules
        untested = self.find_untested_core_modules()
        if untested:
            actions.append(f"Identified {len(untested)} candidate untested core modules (e.g. {untested[0]})")
        else:
            actions.append("All core modules have corresponding test suites")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        result = DaemonCycleResult(
            cycle_id=cycle_id,
            timestamp=time.time(),
            idle_detected=True,
            uncompiled_pairs_count=uncompiled_count,
            dpo_batch_exported=dpo_exported,
            dpo_export_path=export_path_str,
            untested_candidates=untested[:5],  # top 5 candidates
            actions_taken=actions,
            duration_ms=duration_ms,
        )

        with self._lock:
            self.history.append(result)

        return result
