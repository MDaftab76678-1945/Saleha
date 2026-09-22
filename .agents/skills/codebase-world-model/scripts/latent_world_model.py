#!/usr/bin/env python3
"""Codebase Latent World Model (JEPA Mental Simulator).

Predicts compiler diagnostics, structural regressions, and test suite impacts
in latent memory before committing changes to disk.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Any

REPO_ROOT = Path(__file__).resolve().parents[4]


class LatentPredictor:
    """Simulates code modification ripple effects in memory."""

    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self.repo_root = repo_root

    def simulate_modification(
        self, target_rel_path: str, proposed_code: str
    ) -> Dict[str, Any]:
        """Mentally simulates effects of replacing target file content with proposed_code."""
        target_path = (self.repo_root / target_rel_path).resolve()
        original_code = (
            target_path.read_text(encoding="utf-8", errors="replace")
            if target_path.exists()
            else ""
        )

        # Step 1: In-memory AST Validity Check
        ast_valid = False
        syntax_diagnostic = None
        try:
            proposed_tree = ast.parse(proposed_code)
            ast_valid = True
        except SyntaxError as e:
            syntax_diagnostic = f"Predicted SyntaxError: {e.msg} at line {e.lineno}"

        if not ast_valid:
            return {
                "status": "SIMULATION_BLOCKED",
                "predicted_outcome": "SYNTAX_FAILURE",
                "risk_score": 1.0,
                "diagnostic": syntax_diagnostic,
                "impacted_tests": [],
            }

        # Step 2: Extract symbol deltas (removed/renamed functions)
        def get_func_signatures(code_str: str) -> Dict[str, List[str]]:
            try:
                tree = ast.parse(code_str)
                sigs = {}
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        sigs[node.name] = [a.arg for a in node.args.args]
                return sigs
            except Exception:
                return {}

        original_funcs = get_func_signatures(original_code)
        proposed_funcs = get_func_signatures(proposed_code)

        removed_functions = set(original_funcs.keys()) - set(proposed_funcs.keys())
        modified_signatures = []
        for fn, args in proposed_funcs.items():
            if fn in original_funcs and original_funcs[fn] != args:
                modified_signatures.append(
                    f"{fn}: changed args from {original_funcs[fn]} to {args}"
                )

        # Step 3: Predict high-risk tests based on broken symbols
        predicted_broken_tests: List[str] = []
        if removed_functions or modified_signatures:
            target_stem = Path(target_rel_path).stem
            test_dir = self.repo_root / "saleha" / "tests"
            if test_dir.exists():
                for test_file in test_dir.glob("test_*.py"):
                    try:
                        content = test_file.read_text(encoding="utf-8", errors="replace")
                        if target_stem in content:
                            for removed_fn in removed_functions:
                                if removed_fn in content:
                                    predicted_broken_tests.append(
                                        f"{test_file.name} (relies on removed '{removed_fn}')"
                                    )
                    except Exception:
                        continue

        risk_score = 0.0
        if removed_functions:
            risk_score += 0.5
        if modified_signatures:
            risk_score += 0.3
        if predicted_broken_tests:
            risk_score += 0.2
        risk_score = min(1.0, risk_score)

        return {
            "status": "SIMULATED",
            "predicted_outcome": "SAFE" if risk_score < 0.4 else "HIGH_REGRESSION_RISK",
            "risk_score": round(risk_score, 2),
            "removed_symbols": sorted(removed_functions),
            "signature_mutations": modified_signatures,
            "predicted_failing_tests": sorted(predicted_broken_tests),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Latent World Model simulation of code changes."
    )
    parser.add_argument("--target", "-t", required=True, help="Target file relative path.")
    parser.add_argument(
        "--code", "-c", required=True, help="Proposed replacement code or file."
    )
    parser.add_argument("--output", "-o", default=None, help="Save simulation JSON.")

    args = parser.parse_args()
    proposed = args.code
    # If code points to a file, read it
    if os.path.isfile(args.code):
        proposed = Path(args.code).read_text(encoding="utf-8", errors="replace")

    predictor = LatentPredictor()
    result = predictor.simulate_modification(args.target, proposed)

    output_str = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Simulation report saved to: {args.output}")
    else:
        print(output_str)

    return 0 if result["risk_score"] < 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
