#!/usr/bin/env python3
"""AST Mutation Testing Engine.

Injects synthetic code defects into AST representation and evaluates whether
the target test suite catches them. Calculates mutation survival scores to
detect brittle or fake unit tests.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

REPO_ROOT = Path(__file__).resolve().parents[4]


class ASTMutator(ast.NodeTransformer):
    """Replaces operators to generate code mutants."""

    def __init__(self, target_mutation_index: int) -> None:
        super().__init__()
        self.target_mutation_index = target_mutation_index
        self.current_mutation_count = 0
        self.mutation_applied: bool = False
        self.description = ""

    def visit_BinOp(self, node: ast.BinOp) -> ast.BinOp:
        if isinstance(node.op, ast.Add):
            if self.current_mutation_count == self.target_mutation_index:
                node.op = ast.Sub()
                self.mutation_applied = True
                self.description = f"Line {node.lineno}: Changed '+' to '-'"
            self.current_mutation_count += 1
        elif isinstance(node.op, ast.Sub):
            if self.current_mutation_count == self.target_mutation_index:
                node.op = ast.Add()
                self.mutation_applied = True
                self.description = f"Line {node.lineno}: Changed '-' to '+'"
            self.current_mutation_count += 1
        return self.generic_visit(node)  # type: ignore[return-value]

    def visit_Compare(self, node: ast.Compare) -> ast.Compare:
        new_ops = []
        for op in node.ops:
            if isinstance(op, ast.Gt):
                if self.current_mutation_count == self.target_mutation_index:
                    new_ops.append(ast.LtE())
                    self.mutation_applied = True
                    self.description = f"Line {node.lineno}: Inverted '>' to '<='"
                else:
                    new_ops.append(op)
                self.current_mutation_count += 1
            elif isinstance(op, ast.Lt):
                if self.current_mutation_count == self.target_mutation_index:
                    new_ops.append(ast.GtE())
                    self.mutation_applied = True
                    self.description = f"Line {node.lineno}: Inverted '<' to '>='"
                else:
                    new_ops.append(op)
                self.current_mutation_count += 1
            elif isinstance(op, ast.Eq):
                if self.current_mutation_count == self.target_mutation_index:
                    new_ops.append(ast.NotEq())
                    self.mutation_applied = True
                    self.description = f"Line {node.lineno}: Inverted '==' to '!='"
                else:
                    new_ops.append(op)
                self.current_mutation_count += 1
            else:
                new_ops.append(op)
        node.ops = new_ops
        return self.generic_visit(node)  # type: ignore[return-value]


def count_potential_mutations(source_code: str) -> int:
    """Counts how many mutation opportunities exist in source AST."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return 0

    mutator = ASTMutator(target_mutation_index=-1)
    mutator.visit(tree)
    return mutator.current_mutation_count


def generate_mutant(source_code: str, mutation_index: int) -> Tuple[str, str]:
    """Applies a single mutation at index and returns mutated code and description."""
    tree = ast.parse(source_code)
    mutator = ASTMutator(target_mutation_index=mutation_index)
    mutated_tree = mutator.visit(tree)
    ast.fix_missing_locations(mutated_tree)
    return ast.unparse(mutated_tree), mutator.description


def run_mutation_audit(
    target_path: Path, test_command: str, max_mutants: int = 5
) -> Dict[str, Any]:
    """Executes mutation testing against target_path and test_command."""
    if not target_path.exists():
        return {"status": "ERROR", "message": f"Target not found: {target_path}"}

    original_code = target_path.read_text(encoding="utf-8", errors="replace")
    total_available = count_potential_mutations(original_code)

    if total_available == 0:
        return {
            "status": "SKIPPED",
            "message": "No mutable binary or comparison operators found in file.",
            "mutation_score": 100.0,
        }

    mutants_to_test = min(total_available, max_mutants)
    killed_count = 0
    survived_count = 0
    mutant_results: List[Dict[str, Any]] = []

    # Backup original file
    backup_path = target_path.with_suffix(".py.bak")
    shutil.copy2(target_path, backup_path)

    try:
        for idx in range(mutants_to_test):
            mutated_code, desc = generate_mutant(original_code, idx)
            target_path.write_text(mutated_code, encoding="utf-8")

            # Execute test command against mutant
            proc = subprocess.run(
                test_command,
                shell=True,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # If test fails, mutant was successfully caught (KILLED)
            if proc.returncode != 0:
                status = "KILLED"
                killed_count += 1
            else:
                status = "SURVIVED"
                survived_count += 1

            mutant_results.append({
                "mutant_id": idx + 1,
                "description": desc,
                "status": status,
                "returncode": proc.returncode,
            })
    finally:
        # Restore original code unconditionally
        if backup_path.exists():
            shutil.copy2(backup_path, target_path)
            backup_path.unlink(missing_ok=True)

    mutation_score = (killed_count / max(mutants_to_test, 1)) * 100.0

    return {
        "status": "COMPLETED",
        "target_file": str(target_path),
        "total_available_mutants": total_available,
        "tested_mutants_count": mutants_to_test,
        "killed_mutants": killed_count,
        "survived_mutants": survived_count,
        "mutation_score_percent": round(mutation_score, 2),
        "rigorous_pass": mutation_score >= 80.0,
        "mutant_records": mutant_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AST Mutation Testing on a target file to verify test rigor."
    )
    parser.add_argument("--target", "-t", required=True, help="Target Python file.")
    parser.add_argument("--test-cmd", "-c", required=True, help="Verification test command.")
    parser.add_argument("--max-mutants", "-m", type=int, default=5, help="Number of mutants to test.")
    parser.add_argument("--output", "-o", default=None, help="Output destination JSON path.")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()
    result = run_mutation_audit(target_path, args.test_cmd, max_mutants=args.max_mutants)

    output_str = json.dumps(result, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Mutation report saved to: {out_path}")
    else:
        print(output_str)

    return 0 if result.get("rigorous_pass", True) else 1


if __name__ == "__main__":
    sys.exit(main())
