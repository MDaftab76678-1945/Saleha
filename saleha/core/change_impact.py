"""
Saleha Core: AST-Based Change Impact Analyzer

Analyzes which functions, classes, and tests are affected by a proposed
code change. Provides "blast radius" estimation before applying any diff.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any


@dataclass
class ImpactReport:
    changed_symbols: List[str]        # functions/classes directly modified
    affected_callers: List[str]       # symbols that call changed symbols
    affected_test_files: List[str]    # test files that test changed symbols
    blast_radius: int                 # 0-100 (100 = entire codebase affected)
    risk_level: str                   # "low" | "medium" | "high" | "critical"
    summary: str


class ChangeImpactAnalyzer:
    """Estimates the blast radius of code changes using AST analysis."""

    def analyze(self, old_content: str, new_content: str,
                file_path: str, repo_root: str = ".") -> ImpactReport:
        """Compute change impact for a modified file."""
        changed_symbols = self._find_changed_symbols(old_content, new_content)
        affected_callers = self._find_callers(changed_symbols, repo_root, file_path)
        affected_tests = self._find_affected_tests(changed_symbols, repo_root)

        # Blast radius: fraction of codebase affected
        total_files = sum(1 for _, _, fs in os.walk(repo_root) for f in fs if f.endswith(".py"))
        affected_count = len(set(affected_callers)) + len(affected_tests)
        blast = min(100, int((affected_count / max(total_files, 1)) * 100) + (10 if changed_symbols else 0))

        if blast >= 60:
            risk = "critical"
        elif blast >= 30:
            risk = "high"
        elif blast >= 10:
            risk = "medium"
        else:
            risk = "low"

        sym_list = ", ".join(changed_symbols[:5]) or "none"
        summary = (f"Changed symbols: [{sym_list}]. "
                   f"{len(affected_callers)} caller(s) affected. "
                   f"{len(affected_tests)} test file(s) affected. "
                   f"Blast radius: {blast}/100.")

        return ImpactReport(
            changed_symbols=changed_symbols,
            affected_callers=affected_callers,
            affected_test_files=affected_tests,
            blast_radius=blast,
            risk_level=risk,
            summary=summary,
        )

    def _find_changed_symbols(self, old_content: str, new_content: str) -> List[str]:
        """Find function/class names that differ between old and new AST."""
        old_syms = self._extract_symbols(old_content)
        new_syms = self._extract_symbols(new_content)

        changed = []
        # New or modified symbols
        for name, src in new_syms.items():
            if name not in old_syms or old_syms[name] != src:
                changed.append(name)
        # Deleted symbols
        for name in old_syms:
            if name not in new_syms:
                changed.append(f"DELETED:{name}")
        return changed

    def _extract_symbols(self, content: str) -> Dict[str, str]:
        """Extract function and class definitions with their source."""
        symbols: Dict[str, str] = {}
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return symbols
        lines = content.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                end = getattr(node, "end_lineno", node.lineno)
                src = "\n".join(lines[node.lineno - 1:end])
                symbols[node.name] = src
        return symbols

    def _find_callers(self, symbol_names: List[str], repo_root: str,
                      exclude_path: str) -> List[str]:
        """Find files that reference any of the changed symbols."""
        clean_names = [s.replace("DELETED:", "") for s in symbol_names]
        callers: Set[str] = set()
        if not clean_names:
            return []
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".venv", "node_modules")]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                if os.path.abspath(fpath) == os.path.abspath(exclude_path):
                    continue
                try:
                    content = open(fpath, "r", encoding="utf-8", errors="replace").read()
                    if any(name in content for name in clean_names):
                        callers.add(os.path.relpath(fpath, repo_root))
                except OSError:
                    continue
        return sorted(callers)

    def _find_affected_tests(self, symbol_names: List[str], repo_root: str) -> List[str]:
        """Find test files that test any of the changed symbols."""
        clean = [s.replace("DELETED:", "") for s in symbol_names]
        tests: Set[str] = set()
        test_dirs = ["tests", "test", os.path.join("saleha", "tests")]
        for test_dir in test_dirs:
            full_dir = os.path.join(repo_root, test_dir)
            if not os.path.isdir(full_dir):
                continue
            for fname in os.listdir(full_dir):
                if not fname.startswith("test_") or not fname.endswith(".py"):
                    continue
                fpath = os.path.join(full_dir, fname)
                try:
                    content = open(fpath, "r", encoding="utf-8", errors="replace").read()
                    if any(name in content for name in clean):
                        tests.add(fname)
                except OSError:
                    continue
        return sorted(tests)


# Global instance
change_impact = ChangeImpactAnalyzer()
