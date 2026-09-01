"""
Saleha Core: Codebase Intelligence & AST Symbol Graph Indexer

Recursively scans codebases, parses Python Abstract Syntax Trees (AST),
extracts symbol tables (classes, methods, functions, imports, docstrings),
tracks cross-file dependency call graphs, and enables surgical diff patching.
"""

from __future__ import annotations

import os
import ast
import re
import difflib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Any, Tuple
from saleha.core.path_utils import safe_relpath


@dataclass
class FunctionSymbol:
    name: str
    args: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    start_line: int = 0
    end_line: int = 0
    calls: List[str] = field(default_factory=list)


@dataclass
class ClassSymbol:
    name: str
    bases: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    methods: Dict[str, FunctionSymbol] = field(default_factory=dict)
    start_line: int = 0
    end_line: int = 0


@dataclass
class FileIndex:
    file_path: str
    relative_path: str
    docstring: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    from_imports: Dict[str, List[str]] = field(default_factory=dict)
    classes: Dict[str, ClassSymbol] = field(default_factory=dict)
    functions: Dict[str, FunctionSymbol] = field(default_factory=dict)
    lines_of_code: int = 0
    syntax_error: Optional[str] = None


class CodebaseIndexer:
    """Scans and indexes a codebase using Python AST parsing."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)
        self.files: Dict[str, FileIndex] = {}
        self.symbol_map: Dict[str, List[str]] = {}  # symbol_name -> list of file paths
        self.ignored_dirs = {
            ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
            "build", "dist", ".egg-info", ".idea", ".vscode", "node_modules",
            ".gemini", "brain", ".system_generated", ".history", "scratch", "site-packages"
        }

    def scan(self) -> Dict[str, FileIndex]:
        """Scans the root directory and indexes all Python files."""
        self.files.clear()
        self.symbol_map.clear()

        for root, dirs, filenames in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            for f in filenames:
                if f.endswith(".py"):
                    full_path = os.path.join(root, f)
                    rel_path = safe_relpath(full_path, self.root_dir)
                    file_index = self._parse_file(full_path, rel_path)
                    self.files[rel_path] = file_index
                    self._register_symbols(rel_path, file_index)

        return self.files

    def _parse_file(self, full_path: str, rel_path: str) -> FileIndex:
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            return FileIndex(
                file_path=full_path, relative_path=rel_path,
                syntax_error=f"Read error: {str(e)}"
            )

        loc = len(content.splitlines())
        try:
            tree = ast.parse(content, filename=full_path)
        except SyntaxError as e:
            return FileIndex(
                file_path=full_path, relative_path=rel_path,
                lines_of_code=loc, syntax_error=f"SyntaxError: {e.msg} (line {e.lineno})"
            )

        docstring = ast.get_docstring(tree)
        imports: List[str] = []
        from_imports: Dict[str, List[str]] = {}
        classes: Dict[str, ClassSymbol] = {}
        functions: Dict[str, FunctionSymbol] = {}

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or "."
                from_imports.setdefault(module, [])
                for alias in node.names:
                    from_imports[module].append(alias.name)
            elif isinstance(node, ast.ClassDef):
                cls_sym = self._parse_class(node)
                classes[cls_sym.name] = cls_sym
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_sym = self._parse_function(node)
                functions[fn_sym.name] = fn_sym

        return FileIndex(
            file_path=full_path,
            relative_path=rel_path,
            docstring=docstring,
            imports=imports,
            from_imports=from_imports,
            classes=classes,
            functions=functions,
            lines_of_code=loc
        )

    def _parse_class(self, node: ast.ClassDef) -> ClassSymbol:
        bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, 'unparse') else []
        methods: Dict[str, FunctionSymbol] = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = self._parse_function(item)
                methods[fn.name] = fn

        return ClassSymbol(
            name=node.name,
            bases=bases,
            docstring=ast.get_docstring(node),
            methods=methods,
            start_line=node.lineno,
            end_line=getattr(node, 'end_lineno', node.lineno)
        )

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionSymbol:
        args = [arg.arg for arg in node.args.args]
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)

        # Collect function calls inside function body
        calls: List[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        return FunctionSymbol(
            name=node.name,
            args=args,
            returns=returns,
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            start_line=node.lineno,
            end_line=getattr(node, 'end_lineno', node.lineno),
            calls=calls
        )

    def _register_symbols(self, rel_path: str, file_index: FileIndex):
        for cls_name, cls_sym in file_index.classes.items():
            self.symbol_map.setdefault(cls_name, []).append(rel_path)
            for m_name in cls_sym.methods:
                self.symbol_map.setdefault(f"{cls_name}.{m_name}", []).append(rel_path)

        for fn_name in file_index.functions:
            self.symbol_map.setdefault(fn_name, []).append(rel_path)

    def find_symbol(self, symbol_name: str) -> List[str]:
        """Returns list of relative file paths where the symbol is defined."""
        return self.symbol_map.get(symbol_name, [])

    def get_summary(self) -> Dict[str, Any]:
        """Returns summary statistics for the scanned codebase."""
        total_files = len(self.files)
        total_loc = sum(f.lines_of_code for f in self.files.values())
        total_classes = sum(len(f.classes) for f in self.files.values())
        total_functions = sum(len(f.functions) + sum(len(c.methods) for c in f.classes.values()) for f in self.files.values())
        errors = [f.relative_path for f in self.files.values() if f.syntax_error]

        return {
            "root_dir": self.root_dir,
            "total_files": total_files,
            "total_loc": total_loc,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "syntax_error_files": errors,
        }


class SmartPatcher:
    """Applies surgical diff patches and validates code syntax before writing."""

    @staticmethod
    def create_unified_diff(original: str, modified: str, filename: str = "file.py") -> str:
        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines, mod_lines,
            fromfile=f"a/{filename}", tofile=f"b/{filename}"
        )
        return "".join(diff)

    @staticmethod
    def fuzzy_find_block(source_lines: List[str], search_lines: List[str]) -> Optional[int]:
        """Finds starting line index in source_lines matching search_lines (with exact or trimmed fallback)."""
        if not search_lines or not source_lines:
            return None
        n_search = len(search_lines)
        if n_search > len(source_lines):
            return None

        # 1. Exact line match
        for i in range(len(source_lines) - n_search + 1):
            if source_lines[i:i + n_search] == search_lines:
                return i

        # 2. Strip trailing whitespace match
        clean_search = [l.rstrip() for l in search_lines]
        for i in range(len(source_lines) - n_search + 1):
            clean_source = [l.rstrip() for l in source_lines[i:i + n_search]]
            if clean_source == clean_search:
                return i

        # 3. Strip leading & trailing whitespace match (indentation-tolerant)
        trimmed_search = [l.strip() for l in search_lines if l.strip()]
        if not trimmed_search:
            return None

        for i in range(len(source_lines)):
            if source_lines[i].strip() == trimmed_search[0]:
                k = 0
                matched_indices = []
                for j in range(i, min(len(source_lines), i + len(search_lines) + 10)):
                    if not source_lines[j].strip() and not (k < len(search_lines) and not search_lines[k].strip()):
                        continue
                    if k < len(trimmed_search) and source_lines[j].strip() == trimmed_search[k]:
                        matched_indices.append(j)
                        k += 1
                        if k == len(trimmed_search):
                            return i
                    elif k > 0:
                        break
        return None

    @staticmethod
    def apply_search_replace(original_code: str, search_block: str, replace_block: str) -> Tuple[bool, str, Optional[str]]:
        """Replaces search_block in original_code with replace_block using exact or fuzzy line matching."""
        if not search_block:
            return False, original_code, "Empty search block"

        if search_block in original_code:
            new_code = original_code.replace(search_block, replace_block, 1)
            return True, new_code, None

        orig_lines = original_code.splitlines(keepends=True)
        search_lines = search_block.splitlines(keepends=True)
        replace_lines = replace_block.splitlines(keepends=True)

        idx = SmartPatcher.fuzzy_find_block(orig_lines, search_lines)
        if idx is not None:
            new_lines = orig_lines[:idx] + replace_lines + orig_lines[idx + len(search_lines):]
            return True, "".join(new_lines), None

        return False, original_code, "Could not match search block in target file."

    @staticmethod
    def parse_aider_blocks(diff_text: str) -> List[Tuple[str, str]]:
        """Extracts (search, replace) block pairs from Aider-style diff text."""
        blocks: List[Tuple[str, str]] = []
        pattern = re.compile(r"<<<<<<<\s*SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>>", re.DOTALL)
        for match in pattern.finditer(diff_text):
            search_part = match.group(1)
            replace_part = match.group(2)
            blocks.append((search_part, replace_part))
        return blocks

    @staticmethod
    def apply_aider_diff(original_code: str, diff_text: str) -> Tuple[bool, str, Optional[str]]:
        """Applies all Aider-style SEARCH/REPLACE blocks sequentially to original_code."""
        blocks = SmartPatcher.parse_aider_blocks(diff_text)
        if not blocks:
            return False, original_code, "No SEARCH/REPLACE blocks found in diff text."

        current_code = original_code
        for i, (search_b, replace_b) in enumerate(blocks):
            ok, new_code, err = SmartPatcher.apply_search_replace(current_code, search_b, replace_b)
            if not ok:
                return False, original_code, f"Block #{i+1} failed to apply: {err}"
            current_code = new_code

        return True, current_code, None

    @staticmethod
    def apply_patch(file_path: str, modified_code: str) -> Dict[str, Any]:
        """Validates syntax of modified_code and safely overwrites file_path."""
        if file_path.endswith(".py"):
            try:
                ast.parse(modified_code)
            except SyntaxError as e:
                return {
                    "success": False,
                    "error": f"Refactored code has syntax error: {e.msg} (line {e.lineno})",
                    "diff": ""
                }

        original_code = ""
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                original_code = f.read()

        diff = SmartPatcher.create_unified_diff(original_code, modified_code, os.path.basename(file_path))

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(modified_code)

        return {
            "success": True,
            "diff": diff,
            "lines_changed": len([l for l in diff.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))])
        }


# Global instance
codebase_indexer = CodebaseIndexer()


