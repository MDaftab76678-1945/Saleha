"""
Saleha Core: Cross-File Dependency Graph & Atomic Multi-File Refactoring Engine.

Constructs an Abstract Syntax Tree (AST) symbol call hierarchy across the entire workspace,
tracks cross-file imports, discovers callers/callees, detects circular dependencies,
computes topological build ordering, and performs safe atomic multi-file edits.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from saleha.core.path_utils import safe_relpath


@dataclass
class SymbolLocation:
    symbol_name: str
    kind: str  # 'function', 'class', 'method'
    file_path: str
    line_number: int
    docstring: str = ""


@dataclass
class SymbolReference:
    symbol_called: str
    caller_file: str
    caller_line: int
    caller_context: str = ""


class _ASTGraphVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.definitions: List[SymbolLocation] = []
        self.references: List[SymbolReference] = []
        self.imports: List[str] = []
        self._current_context: str = "module"
        self._scope_stack: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            if mod:
                self.imports.append(f"{mod}.{alias.name}")
            else:
                self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        doc = ast.get_docstring(node) or ""
        self.definitions.append(
            SymbolLocation(
                symbol_name=node.name,
                kind="class",
                file_path=self.file_path,
                line_number=node.lineno,
                docstring=doc,
            )
        )
        self._scope_stack.append(node.name)
        old_ctx = self._current_context
        self._current_context = f"class {node.name}"
        self.generic_visit(node)
        self._current_context = old_ctx
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        doc = ast.get_docstring(node) or ""
        is_method = len(self._scope_stack) > 0
        kind = "method" if is_method else "function"

        # Flat symbol definition (backward-compatible)
        self.definitions.append(
            SymbolLocation(
                symbol_name=node.name,
                kind=kind,
                file_path=self.file_path,
                line_number=node.lineno,
                docstring=doc,
            )
        )

        # Class-scoped method symbol definition
        if is_method:
            scoped_name = f"{'.'.join(self._scope_stack)}.{node.name}"
            self.definitions.append(
                SymbolLocation(
                    symbol_name=scoped_name,
                    kind="method",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    docstring=doc,
                )
            )

        old_ctx = self._current_context
        self._current_context = f"func {node.name}"
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()
        self._current_context = old_ctx

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name:
            self.references.append(
                SymbolReference(
                    symbol_called=func_name,
                    caller_file=self.file_path,
                    caller_line=node.lineno,
                    caller_context=self._current_context,
                )
            )
        self.generic_visit(node)


class CodebaseDependencyGraph:
    """Builds and queries cross-file symbol call hierarchies and dependency maps."""

    def __init__(self, root_dir: str = ".") -> None:
        self.root_dir = os.path.abspath(root_dir)
        self.definitions: Dict[str, List[SymbolLocation]] = {}
        self.references: Dict[str, List[SymbolReference]] = {}
        self.file_imports: Dict[str, List[str]] = {}
        self.files_indexed: Set[str] = set()

    def build_graph(self, root_dir: Optional[str] = None) -> Dict[str, Any]:
        """Indexes all Python files in the workspace to construct call graphs."""
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)

        self.definitions.clear()
        self.references.clear()
        self.file_imports.clear()
        self.files_indexed.clear()

        for root, _, files in os.walk(self.root_dir):
            rel_parts = safe_relpath(root, self.root_dir).split(os.sep)
            if any(
                (p.startswith(".") and p not in (".", ".."))
                or p in ("node_modules", "venv", "__pycache__", "build", "dist", ".git")
                for p in rel_parts
            ):
                continue

            for f in files:
                if f.endswith(".py"):
                    full_path = os.path.join(root, f)
                    rel_path = safe_relpath(full_path, self.root_dir).replace("\\", "/")
                    self._index_file(full_path, rel_path)

        return {
            "total_files": len(self.files_indexed),
            "total_definitions": sum(len(v) for v in self.definitions.values()),
            "total_references": sum(len(v) for v in self.references.values()),
        }

    def _index_file(self, full_path: str, rel_path: str) -> None:
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            tree = ast.parse(code, filename=rel_path)
            visitor = _ASTGraphVisitor(rel_path)
            visitor.visit(tree)

            self.files_indexed.add(rel_path)
            self.file_imports[rel_path] = visitor.imports

            for d in visitor.definitions:
                self.definitions.setdefault(d.symbol_name, []).append(d)

            for r in visitor.references:
                self.references.setdefault(r.symbol_called, []).append(r)
        except Exception:
            pass

    def find_callers(self, symbol_name: str) -> List[SymbolReference]:
        """Finds all code references calling or instantiating a symbol."""
        return self.references.get(symbol_name, [])

    def find_callees(self, symbol_name: str) -> List[SymbolReference]:
        """Finds every call made from inside a given function/method body.

        The module docstring has claimed callee discovery since this class
        was written; only find_callers existed. `_ASTGraphVisitor` already
        records `caller_context` (the enclosing function name) on every
        `SymbolReference` it collects, so this needed no new AST pass --
        just filtering the same references by that field instead of by
        `symbol_called`. `caller_context` is unqualified (`func foo`, not
        `func Class.foo`), so a method name shared by two classes returns
        both bodies' calls; callers needing one specific class should also
        check `caller_file`.
        """
        needle = f"func {symbol_name}"
        out: List[SymbolReference] = []
        for refs in self.references.values():
            out.extend(r for r in refs if r.caller_context == needle)
        out.sort(key=lambda r: (r.caller_file, r.caller_line))
        return out

    def find_definitions(self, symbol_name: str) -> List[SymbolLocation]:
        """Finds where a symbol is defined in the codebase."""
        return self.definitions.get(symbol_name, [])

    def _resolve_import_to_file(self, import_str: str) -> Optional[str]:
        """Resolves an import name to a registered file in the workspace."""
        parts = import_str.split(".")
        for i in range(len(parts), 0, -1):
            candidate = "/".join(parts[:i])
            f_cand = f"{candidate}.py"
            init_cand = f"{candidate}/__init__.py"
            for indexed in self.files_indexed:
                if indexed == f_cand or indexed == init_cand or indexed.endswith("/" + f_cand) or indexed.endswith("/" + init_cand):
                    return indexed
        return None

    def get_file_dependency_graph(self) -> Dict[str, Set[str]]:
        """Returns direct file-to-file dependency mapping (file -> set of imported workspace files)."""
        graph: Dict[str, Set[str]] = {f: set() for f in self.files_indexed}
        for file_path, imports in self.file_imports.items():
            for imp in imports:
                resolved = self._resolve_import_to_file(imp)
                if resolved and resolved != file_path:
                    graph[file_path].add(resolved)
        return graph

    def detect_cycles(self) -> List[List[str]]:
        """
        Detects circular dependencies in the file import graph using iterative
        DFS cycle traversal.

        The recursive implementation crashed on workspaces with more than ~1000
        Python files in a single import chain -- Python's default recursion limit
        is 1000, and the saleha/core directory alone already has 252 modules.
        An explicit stack replaces the call stack, so depth is bounded only by
        heap memory.

        Returns a list of cycle paths, e.g. [['a.py', 'b.py', 'a.py']].
        """
        adj = self.get_file_dependency_graph()
        # 0: unvisited, 1: on stack (visiting), 2: done
        visited: Dict[str, int] = {}
        cycles: List[List[str]] = []

        for start in sorted(self.files_indexed):
            if visited.get(start, 0) != 0:
                continue

            # Each stack frame: (node, iterator-over-neighbors, path-snapshot)
            # We push (node, neighbors_iter, current_path) tuples.
            path: List[str] = []
            stack: List[tuple] = [(start, iter(sorted(adj.get(start, set()))), path)]
            visited[start] = 1
            path.append(start)

            while stack:
                node, neighbors, _ = stack[-1]
                try:
                    neighbor = next(neighbors)
                    state = visited.get(neighbor, 0)
                    if state == 1:
                        # Back edge: cycle found
                        cycle_start = path.index(neighbor)
                        cycles.append(path[cycle_start:] + [neighbor])
                    elif state == 0:
                        visited[neighbor] = 1
                        path.append(neighbor)
                        stack.append((neighbor,
                                      iter(sorted(adj.get(neighbor, set()))),
                                      path))
                except StopIteration:
                    visited[node] = 2
                    path.pop()
                    stack.pop()

        return cycles

    def get_topological_order(self) -> List[str]:
        """
        Returns a topologically sorted order of workspace files.
        Files with no dependencies on other workspace files appear first.
        In the presence of cycles, cycle nodes are placed gracefully at the end.
        """
        adj = self.get_file_dependency_graph()
        # Calculate in-degree: number of workspace files a file depends on
        in_degree: Dict[str, int] = {f: len(adj.get(f, set())) for f in self.files_indexed}
        # Build reverse mapping: who depends on f?
        dependents: Dict[str, Set[str]] = {f: set() for f in self.files_indexed}
        for u, neighbors in adj.items():
            for v in neighbors:
                dependents.setdefault(v, set()).add(u)

        queue = sorted([f for f, deg in in_degree.items() if deg == 0])
        ordered: List[str] = []

        while queue:
            node = queue.pop(0)
            ordered.append(node)
            for dep in sorted(dependents.get(node, set())):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
            queue.sort()

        # If cycles exist, append any remaining nodes
        remaining = sorted([f for f in self.files_indexed if f not in ordered])
        ordered.extend(remaining)
        return ordered

    def get_unresolved_imports(self) -> Dict[str, List[str]]:
        """Returns internal imports from workspace files that cannot be resolved."""
        unresolved: Dict[str, List[str]] = {}
        for f, imps in self.file_imports.items():
            missing = []
            for imp in imps:
                # Check if it looks like an internal project import (starts with workspace top-level names)
                first_part = imp.split(".")[0]
                has_prefix = any(idx.startswith(first_part + "/") or idx == f"{first_part}.py" for idx in self.files_indexed)
                if has_prefix and not self._resolve_import_to_file(imp):
                    missing.append(imp)
            if missing:
                unresolved[f] = missing
        return unresolved

    def get_impacted_files(self, file_path: str) -> List[str]:
        """Identifies downstream files that import or reference symbols defined in this file."""
        rel_path = safe_relpath(file_path, self.root_dir).replace("\\", "/")
        defined_symbols = set()
        for sym, locs in self.definitions.items():
            if any(loc.file_path == rel_path for loc in locs):
                defined_symbols.add(sym)

        impacted = set()
        for sym in defined_symbols:
            for ref in self.references.get(sym, []):
                if ref.caller_file != rel_path:
                    impacted.add(ref.caller_file)

        return sorted(list(impacted))

    def atomic_multi_file_patch(self, patches: Dict[str, str]) -> Dict[str, Any]:
        """
        Validates AST syntax of all patched files before applying, ensuring atomic all-or-nothing writes.
        """
        # Step 1: Pre-validation of syntax
        errors = {}
        for file_path, new_content in patches.items():
            if file_path.endswith(".py"):
                try:
                    ast.parse(new_content, filename=file_path)
                except SyntaxError as e:
                    errors[file_path] = f"SyntaxError at line {e.lineno}: {e.msg}"

        if errors:
            return {
                "success": False,
                "error": "Atomic patch aborted: Syntax validation failed.",
                "details": errors,
            }

        # Step 2: Backup and apply
        backups = {}
        try:
            for file_path, new_content in patches.items():
                abs_path = os.path.abspath(file_path)
                if os.path.isfile(abs_path):
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        backups[abs_path] = f.read()
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            return {
                "success": True,
                "patched_files": list(patches.keys()),
                "count": len(patches),
            }
        except Exception as e:
            # Rollback all changes
            for abs_path, old_content in backups.items():
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(old_content)
            return {
                "success": False,
                "error": f"Atomic patch failed and rolled back: {str(e)}",
            }


# Global singleton instance
dependency_graph = CodebaseDependencyGraph()
