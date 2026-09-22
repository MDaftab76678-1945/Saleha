#!/usr/bin/env python3
"""Active Inference Execution Engine.

Iteratively samples sensory observations from the code execution environment
and drives agent actions to minimize free energy (divergence between desired
and observed state).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add repository root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from saleha.core.verification.quality_guard import QualityGuard


class ActiveInferenceAgent:
    """Active inference controller for code synthesis and verification."""

    def __init__(self, target_path: Path, max_iterations: int = 5) -> None:
        self.target_path = target_path
        self.max_iterations = max_iterations
        self.guard = QualityGuard()
        self.history: List[Dict[str, Any]] = []

    def sample_observation(self, test_command: Optional[str] = None) -> Dict[str, Any]:
        """Gathers physical evidence: AST quality status and optional test runner output."""
        if not self.target_path.exists():
            return {
                "exists": False,
                "ast_clean": False,
                "ast_errors": [f"File not found: {self.target_path}"],
                "test_passed": False,
                "free_energy": 100.0,
            }

        report = self.guard.check_file(str(self.target_path))

        ast_errors = [
            issue.message for issue in report.issues if issue.severity in ("CRITICAL", "MAJOR")
        ]
        ast_clean = report.passed

        test_passed = True
        test_output = ""
        if test_command:
            proc = subprocess.run(
                test_command,
                shell=True,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            test_passed = proc.returncode == 0
            test_output = proc.stdout if test_passed else proc.stderr

        # Variational Free Energy = (AST error count * 10) + (Test failure penalty)
        free_energy = float(len(ast_errors) * 10.0 + (0.0 if test_passed else 50.0))

        return {
            "exists": True,
            "ast_clean": ast_clean,
            "ast_errors": ast_errors,
            "test_passed": test_passed,
            "test_output": test_output[:400] if test_output else "",
            "free_energy": free_energy,
        }

    def run_cycle(self, test_command: Optional[str] = None) -> Dict[str, Any]:
        """Executes active inference cycles until free energy reaches zero or limit hit."""
        for iteration in range(1, self.max_iterations + 1):
            obs = self.sample_observation(test_command)
            step_record = {
                "iteration": iteration,
                "free_energy": obs["free_energy"],
                "ast_clean": obs["ast_clean"],
                "test_passed": obs["test_passed"],
                "ast_errors": obs["ast_errors"],
            }
            self.history.append(step_record)

            if obs["free_energy"] == 0.0:
                return {
                    "status": "CONVERGED",
                    "iterations_taken": iteration,
                    "final_free_energy": 0.0,
                    "target_file": str(self.target_path),
                    "history": self.history,
                }

            # If not converged and consecutive iterations show identical error (attractor basin)
            if (
                len(self.history) >= 2
                and self.history[-1]["free_energy"] == self.history[-2]["free_energy"]
            ):
                step_record["action"] = "PHASE_RESET_REQUIRED"

        return {
            "status": "DIVERGED",
            "iterations_taken": self.max_iterations,
            "final_free_energy": self.history[-1]["free_energy"],
            "target_file": str(self.target_path),
            "history": self.history,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Active Inference convergence cycle for a target module."
    )
    parser.add_argument("--target", "-t", required=True, help="Target Python file.")
    parser.add_argument("--test-cmd", "-c", default=None, help="Optional verification test command.")
    parser.add_argument("--max-iter", "-m", type=int, default=5, help="Maximum loop iterations.")
    parser.add_argument("--output", "-o", default=None, help="Optional output JSON file path.")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()
    agent = ActiveInferenceAgent(target_path, max_iterations=args.max_iter)
    result = agent.run_cycle(test_command=args.test_cmd)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Inference record written to: {out_path}")
    else:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] == "CONVERGED" else 1


if __name__ == "__main__":
    sys.exit(main())
