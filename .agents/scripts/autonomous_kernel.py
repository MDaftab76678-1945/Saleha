#!/usr/bin/env python3
"""Saleha Autonomous Master Kernel.

Coordinates the closed-loop autonomic execution pipeline:
Input Task -> Blast Radius Analysis -> CPG Slicing -> Blackboard Arbitration
-> Sandbox Jail -> Quality Gate -> Flight Recorder.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add repository root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from saleha.core.verification.quality_guard import QualityGuard

# Import helper engines from .agents/scripts
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flight_recorder import FlightRecorder
from cpg_slicer import compute_backward_slice
from hypergraph_impact import compute_blast_radius


class AutonomousKernel:
    """Central closed-loop coordinator for autonomous tasks."""

    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self.repo_root = repo_root
        self.recorder = FlightRecorder()
        self.guard = QualityGuard()

    def execute_task_cycle(
        self,
        target_file: str,
        target_line: Optional[int] = None,
        test_command: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs an end-to-end autonomic cycle for target_file."""
        self.recorder.record_event(
            "CYCLE_START", "INITIALIZE", {"target_file": target_file, "target_line": target_line}
        )

        abs_target = (self.repo_root / target_file).resolve()
        if not abs_target.exists():
            res = {"status": "FAILED", "stage": "VALIDATE_TARGET", "error": "Target does not exist"}
            self.recorder.record_event("CYCLE_FAILED", "VALIDATE_TARGET", res, status="ERROR")
            return res

        # Stage 1: Blast Radius & Impact Calculation
        impact = compute_blast_radius(target_file, self.repo_root)
        self.recorder.record_event(
            "IMPACT_ANALYSIS",
            "BLAST_RADIUS",
            {
                "severity": impact["blast_radius_severity"],
                "affected_files": impact["total_affected_files"],
                "dependent_tests": impact["dependent_tests"],
            },
        )

        # Stage 2: CPG Slicing for Context Budgeting
        code_text = abs_target.read_text(encoding="utf-8", errors="replace")
        slicing_info = None
        if target_line is not None and 1 <= target_line <= len(code_text.splitlines()):
            slice_res = compute_backward_slice(code_text, target_line)
            if slice_res.get("status") == "success":
                slicing_info = {
                    "sliced_lines": slice_res["sliced_lines_count"],
                    "reduction_percent": slice_res["reduction_percent"],
                }
                self.recorder.record_event("CONTEXT_SLICING", "CPG_REDUCTION", slicing_info)

        # Stage 3: Quality Guard Pre-Flight Verification
        report = self.guard.check_file(str(abs_target))
        quality_passed = report.passed
        quality_score = report.quality_score
        quality_issues = [
            f"Line {i.line_number}: [{i.severity}] {i.message}"
            for i in report.issues
            if i.severity in ("CRITICAL", "MAJOR")
        ]

        self.recorder.record_event(
            "QUALITY_GATE",
            "AST_AUDIT",
            {
                "passed": quality_passed,
                "score": quality_score,
                "critical_issues": quality_issues,
            },
            status="SUCCESS" if quality_passed else "WARNING",
        )

        # Stage 4: Test Verification Guidance
        recommended_cmd = impact.get("recommended_test_command", "python -m pytest saleha/tests/ -q")
        if test_command:
            recommended_cmd = test_command

        cycle_summary = {
            "status": "COMPLETED" if quality_passed else "QUALITY_BLOCKED",
            "target_file": target_file,
            "blast_radius_severity": impact["blast_radius_severity"],
            "affected_tests_count": len(impact["dependent_tests"]),
            "cpg_reduction": slicing_info,
            "quality_score": quality_score,
            "quality_passed": quality_passed,
            "critical_issues": quality_issues,
            "recommended_test_command": recommended_cmd,
        }

        self.recorder.record_event(
            "CYCLE_COMPLETE",
            "FINALIZE",
            cycle_summary,
            status="SUCCESS" if quality_passed else "BLOCKED",
        )
        return cycle_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Saleha Autonomous Master Kernel CLI.")
    parser.add_argument("--file", "-f", required=True, help="Target file for autonomous pipeline.")
    parser.add_argument("--line", "-l", type=int, default=None, help="Target line for CPG backward slicing.")
    parser.add_argument("--test-cmd", "-c", default=None, help="Optional test command.")
    parser.add_argument("--output", "-o", default=None, help="Save execution telemetry JSON.")

    args = parser.parse_args()
    kernel = AutonomousKernel()
    result = kernel.execute_task_cycle(args.file, target_line=args.line, test_command=args.test_cmd)

    output_str = json.dumps(result, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Kernel execution telemetry saved to: {out_path}")
    else:
        print(output_str)

    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
