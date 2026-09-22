#!/usr/bin/env python3
"""Hypergraph Blast-Radius & Dependency Impact Engine.

Calculates multi-dimensional ripple effects across Modules, Functions, Tests,
and Invariants when a source file is modified. Prevents unexpected regressions
and guides surgical test validation.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Any


class DependencyScanner(ast.NodeVisitor):
    """Extracts imported modules and top-level function/class definitions."""

    def __init__(self, current_module: str) -> None:
        self.current_module = current_module
        self.imports: Set[str] = set()
        self.definitions: Set[str] = set()
        self.called_functions: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.add(node.module)
            for alias in node.names:
                self.imports.add(f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.definitions.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.definitions.add(node.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.called_functions.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_functions.add(node.func.attr)
        self.generic_visit(node)


def build_repo_dependency_hypergraph(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    """Scans all Python files across repo and constructs module dependency map."""
    graph: Dict[str, Dict[str, Any]] = {}

    for path in repo_root.rglob("*.py"):
        # Ignore virtual environments, git directories, and caches
        rel_parts = path.relative_to(repo_root).parts
        if any(p.startswith(".") or p.startswith(".venv") or p == "__pycache__" for p in rel_parts):
            continue

        mod_name = ".".join(path.relative_to(repo_root).with_suffix("").parts)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue

        scanner = DependencyScanner(mod_name)
        scanner.visit(tree)

        graph[mod_name] = {
            "path": str(path.relative_to(repo_root)).replace("\\", "/"),
            "imports": sorted(scanner.imports),
            "definitions": sorted(scanner.definitions),
            "calls": sorted(scanner.called_functions),
            "is_test": "test" in path.name.lower() or "tests" in rel_parts,
        }

    return graph


def compute_blast_radius(target_file: str, repo_root: Path) -> Dict[str, Any]:
    """Computes the direct and transitive blast radius of modifying target_file."""
    norm_target = target_file.replace("\\", "/").lstrip("./")
    graph = build_repo_dependency_hypergraph(repo_root)

    # Resolve target module in graph
    target_mod = None
    target_defs: Set[str] = set()
    for mod, data in graph.items():
        if data["path"] == norm_target or norm_target.endswith(data["path"]):
            target_mod = mod
            target_defs = set(data["definitions"])
            break

    target_stem = Path(norm_target).stem
    dependent_modules: Set[str] = set()
    dependent_tests: Set[str] = set()
    affected_callers: Set[str] = set()

    for mod, data in graph.items():
        if mod == target_mod:
            continue

        # Direct import match
        is_dependent = False
        if target_mod and any(target_mod in imp for imp in data["imports"]):
            is_dependent = True
        elif target_stem in data["imports"] or any(target_stem in imp for imp in data["imports"]):
            is_dependent = True

        # Functional call intersection
        called_intersection = target_defs.intersection(data["calls"])
        if called_intersection:
            is_dependent = True
            affected_callers.add(f"{data['path']} -> calls: {', '.join(called_intersection)}")

        if is_dependent:
            if data["is_test"]:
                dependent_tests.add(data["path"])
            else:
                dependent_modules.add(data["path"])

    # Score blast radius
    total_affected = len(dependent_modules) + len(dependent_tests)
    if total_affected == 0:
        severity = "MINIMAL"
    elif total_affected <= 3:
        severity = "LOW"
    elif total_affected <= 8:
        severity = "MODERATE"
    elif total_affected <= 15:
        severity = "HIGH"
    else:
        severity = "CRITICAL"

    return {
        "status": "success",
        "target_file": norm_target,
        "target_module": target_mod or "unresolved",
        "total_defined_symbols": len(target_defs),
        "blast_radius_severity": severity,
        "total_affected_files": total_affected,
        "dependent_modules": sorted(dependent_modules),
        "dependent_tests": sorted(dependent_tests),
        "affected_call_sites": sorted(affected_callers),
        "recommended_test_command": (
            f"python -m pytest {' '.join(sorted(dependent_tests))} -v"
            if dependent_tests
            else "python -m pytest saleha/tests/ -q"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute hypergraph blast radius and dependent test suites for code changes."
    )
    parser.add_argument("--file", "-f", required=True, help="Target file path to analyze.")
    parser.add_argument("--repo-root", "-r", type=str, default=".", help="Repository root path.")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON format.")
    parser.add_argument("--output", "-o", type=str, default=None, help="Save report to file.")

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    result = compute_blast_radius(args.file, repo_root)

    if args.json:
        out_str = json.dumps(result, indent=2)
    else:
        lines = [
            "===========================================================",
            f"  SALEHA HYPERGRAPH BLAST-RADIUS AUDIT REPORT",
            "===========================================================",
            f" Target File       : {result['target_file']}",
            f" Module            : {result['target_module']}",
            f" Impact Severity   : {result['blast_radius_severity']}",
            f" Affected Files    : {result['total_affected_files']}",
            "-----------------------------------------------------------",
            f" Dependent Code Modules ({len(result['dependent_modules'])}):",
        ]
        for m in result["dependent_modules"]:
            lines.append(f"   [+] {m}")

        lines.append(f"\n Dependent Test Suites ({len(result['dependent_tests'])}):")
        for t in result["dependent_tests"]:
            lines.append(f"   [*] {t}")

        lines.append("\n Direct Call Sites:")
        for c in result["affected_call_sites"][:10]:
            lines.append(f"   - {c}")
        if len(result["affected_call_sites"]) > 10:
            lines.append(f"   ... and {len(result['affected_call_sites']) - 10} more")

        lines.append("-----------------------------------------------------------")
        lines.append(f" Recommended Verification Command:\n  {result['recommended_test_command']}")
        lines.append("===========================================================")
        out_str = "\n".join(lines)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_str, encoding="utf-8")
        print(f"Report saved to: {out_path}")
    else:
        print(out_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
