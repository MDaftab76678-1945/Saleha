"""
Saleha Core: Cross-File Dependency Graph & Atomic Multi-File Refactoring Engine

Constructs an Abstract Syntax Tree (AST) symbol call hierarchy across the entire workspace,
tracks cross-file imports, discovers callers/callees, and performs safe atomic multi-file edits.
"""

import ast
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
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
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.definitions: List[SymbolLocation] = []
        self.references: List[SymbolReference] = []
        self.imports: List[str] = []
        self._current_context = "module"

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.imports.append(f"{mod}.{alias.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        doc = ast.get_docstring(node) or ""
        self.definitions.append(SymbolLocation(
            symbol_name=node.name,
            kind="class",
            file_path=self.file_path,
            line_number=node.lineno,
            docstring=doc
        ))
        old_ctx = self._current_context
        self._current_context = f"class {node.name}"
        self.generic_visit(node)
        self._current_context = old_ctx

    def visit_FunctionDef(self, node: ast.FunctionDef):
        doc = ast.get_docstring(node) or ""
        kind = "method" if "class " in self._current_context else "function"
        self.definitions.append(SymbolLocation(
            symbol_name=node.name,
            kind=kind,
            file_path=self.file_path,
            line_number=node.lineno,
            docstring=doc
        ))
        old_ctx = self._current_context
        self._current_context = f"func {node.name}"
        self.generic_visit(node)
        self._current_context = old_ctx

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name:
            self.references.append(SymbolReference(
                symbol_called=func_name,
                caller_file=self.file_path,
                caller_line=node.lineno,
                caller_context=self._current_context
            ))
        self.generic_visit(node)


class CodebaseDependencyGraph:
    """Builds and queries cross-file symbol call hierarchies and dependency maps."""

    def __init__(self, root_dir: str = "."):
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
            if any((p.startswith(".") and p not in (".", "..")) or p in ("node_modules", "venv", "__pycache__", "build", "dist", ".git") for p in rel_parts):
                continue

            for f in files:
                if f.endswith(".py"):
                    full_path = os.path.join(root, f)
                    rel_path = safe_relpath(full_path, self.root_dir).replace("\\", "/")
                    self._index_file(full_path, rel_path)

        return {
            "total_files": len(self.files_indexed),
            "total_definitions": sum(len(v) for v in self.definitions.values()),
            "total_references": sum(len(v) for v in self.references.values())
        }

    def _index_file(self, full_path: str, rel_path: str):
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

    def find_definitions(self, symbol_name: str) -> List[SymbolLocation]:
        """Finds where a symbol is defined in the codebase."""
        return self.definitions.get(symbol_name, [])

    def get_impacted_files(self, file_path: str) -> List[str]:
        """Identifies downstream files that import or reference symbols defined in this file."""
        rel_path = safe_relpath(file_path, self.root_dir).replace("\\", "/")
        defined_symbols = set()
        for sym, locs in self.definitions.items():
            if any(l.file_path == rel_path for l in locs):
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
            return {"success": False, "error": "Atomic patch aborted: Syntax validation failed.", "details": errors}

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
                "count": len(patches)
            }
        except Exception as e:
            # Rollback all changes
            for abs_path, old_content in backups.items():
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(old_content)
            return {"success": False, "error": f"Atomic patch failed and rolled back: {str(e)}"}


# Global instance
dependency_graph = CodebaseDependencyGraph()

