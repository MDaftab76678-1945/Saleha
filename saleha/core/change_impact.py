"""
Saleha Core: AST-Based Change Impact Analyzer

Analyzes which functions, classes, and tests are affected by a proposed
code change. Provides "blast radius" estimation before applying any diff.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any


@dataclass
class ImpactReport:
    changed_symbols: List[str]        # functions/classes directly modified
    affected_callers: List[str]       # files/symbols that call changed symbols
    affected_test_files: List[str]    # test files that test changed symbols
    blast_radius: int                 # 0-100 (100 = entire codebase affected)
    risk_level: str                   # "low" | "medium" | "high" | "critical"
    summary: str


class _ScopedSymbolExtractor(ast.NodeVisitor):
    """Scoped AST extractor capturing classes, functions, and qualified methods."""

    def __init__(self, lines: List[str]) -> None:
        self.lines: List[str] = lines
        self.symbols: Dict[str, str] = {}
        self._scope_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        end = getattr(node, "end_lineno", node.lineno)
        src = "\n".join(self.lines[node.lineno - 1:end])
        scope_prefix = ".".join(self._scope_stack)
        full_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name
        self.symbols[full_name] = src
        if full_name != node.name and node.name not in self.symbols:
            self.symbols[node.name] = src

        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_func(node)

    def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        end = getattr(node, "end_lineno", node.lineno)
        src = "\n".join(self.lines[node.lineno - 1:end])
        scope_prefix = ".".join(self._scope_stack)
        full_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name
        self.symbols[full_name] = src
        if full_name != node.name and node.name not in self.symbols:
            self.symbols[node.name] = src

        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()


class ChangeImpactAnalyzer:
    """Estimates the blast radius of code changes using AST and symbol graph analysis."""

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
        """Extract scoped function and class definitions with their source lines."""
        symbols: Dict[str, str] = {}
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return symbols

        lines = content.splitlines()
        extractor = _ScopedSymbolExtractor(lines)
        extractor.visit(tree)
        return extractor.symbols

    def _matches_symbols_in_file(self, fpath: str, targets: Set[str]) -> bool:
        """Determines if a python file actually references any target symbol without false positives."""
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return False

        # Attempt precise AST inspection
        try:
            tree = ast.parse(content)
            referenced: Set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    referenced.add(node.id)
                elif isinstance(node, ast.Attribute):
                    referenced.add(node.attr)
                elif isinstance(node, ast.alias):
                    referenced.add(node.name.split(".")[-1])
                    if node.asname:
                        referenced.add(node.asname)
            return bool(referenced.intersection(targets))
        except Exception:
            # Fallback for non-parsable files: strict word-boundary regex (no substring bleeding)
            for t in targets:
                if re.search(rf"\b{re.escape(t)}\b", content):
                    return True
            return False

    def _find_callers(self, symbol_names: List[str], repo_root: str,
                      exclude_path: str) -> List[str]:
        """Find files that reference any of the changed symbols using exact symbol matching."""
        raw_targets = [s.replace("DELETED:", "") for s in symbol_names]
        if not raw_targets:
            return []

        # Target tokens include both qualified name and leaf identifier
        target_tokens: Set[str] = set()
        for s in raw_targets:
            target_tokens.add(s)
            leaf = s.split(".")[-1]
            if leaf:
                target_tokens.add(leaf)

        callers: Set[str] = set()
        norm_exclude = os.path.abspath(exclude_path) if exclude_path else ""

        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".venv", "node_modules")]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                if norm_exclude and os.path.abspath(fpath) == norm_exclude:
                    continue
                if self._matches_symbols_in_file(fpath, target_tokens):
                    callers.add(os.path.relpath(fpath, repo_root).replace("\\", "/"))

        return sorted(callers)

    def _find_affected_tests(self, symbol_names: List[str], repo_root: str) -> List[str]:
        """Find test files that test any of the changed symbols."""
        clean = [s.replace("DELETED:", "") for s in symbol_names]
        if not clean:
            return []

        target_tokens: Set[str] = set()
        for s in clean:
            target_tokens.add(s)
            leaf = s.split(".")[-1]
            if leaf:
                target_tokens.add(leaf)

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
                if self._matches_symbols_in_file(fpath, target_tokens):
                    tests.add(fname)

        return sorted(tests)


# Global instance
change_impact = ChangeImpactAnalyzer()
