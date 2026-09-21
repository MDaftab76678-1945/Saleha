"""
Saleha Core: Codebase Intelligence & AST Symbol Graph Indexer

Recursively scans codebases, parses Python Abstract Syntax Trees (AST),
extracts symbol tables (classes, methods, functions, imports, docstrings),
tracks cross-file dependency call graphs, and enables surgical diff patching.
"""

from __future__ import annotations

import ast
import difflib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

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

    def __init__(self, root_dir: str = ".") -> None:
        self.root_dir = os.path.abspath(root_dir)
        self.files: Dict[str, FileIndex] = {}
        self.symbol_map: Dict[str, List[str]] = {}  # symbol_name -> list of file paths
        # bare_method_name -> ["ClassName.method_name", ...]. Separate from
        # symbol_map so a bare method lookup can never shadow a same-named
        # top-level function -- find_symbol() only consults this on a miss.
        self.bare_method_map: Dict[str, List[str]] = {}
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

    def _register_symbols(self, rel_path: str, file_index: FileIndex) -> None:
        for cls_name, cls_sym in file_index.classes.items():
            self.symbol_map.setdefault(cls_name, []).append(rel_path)
            for m_name in cls_sym.methods:
                self.symbol_map.setdefault(f"{cls_name}.{m_name}", []).append(rel_path)
                # Bare method names are also registered, distinct from the
                # qualified map. A caller asking for a test function it just
                # read out of a traceback ("test_super_len_with_tell") has
                # no way to know its class name yet -- measured against a
                # real repo bug, find_symbols on the bare method name
                # returned "not found in codebase" even though the method
                # exists, because only "ClassName.method" was ever
                # registered. See find_symbol() for how the two maps are
                # combined without a bare name silently shadowing a
                # same-named top-level function.
                self.bare_method_map.setdefault(m_name, []).append(
                    f"{cls_name}.{m_name}")

        for fn_name in file_index.functions:
            self.symbol_map.setdefault(fn_name, []).append(rel_path)

    def find_symbol(self, symbol_name: str) -> List[str]:
        """Returns list of relative file paths where the symbol is defined.

        Tries an exact match first (a top-level function, a class, or an
        already-qualified "ClassName.method"). Falls back to a bare method
        name match across all classes only when the exact lookup misses, so
        a top-level function is never shadowed by a same-named method.
        """
        exact = self.symbol_map.get(symbol_name, [])
        if exact:
            return exact
        qualified = self.bare_method_map.get(symbol_name, [])
        if not qualified:
            return []
        files: List[str] = []
        for q in qualified:
            files.extend(self.symbol_map.get(q, []))
        # De-duplicate while preserving order (multiple classes across
        # files can share a method name, e.g. every TestCase's setUp).
        seen: Set[str] = set()
        out = []
        for f in files:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

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

    @staticmethod
    def apply_aider_diff(original_code: str, diff_text: str) -> Tuple[bool, str, Optional[str]]:
        return SmartPatcher.apply_aider_diff(original_code, diff_text)

    @staticmethod
    def apply_search_replace(original_code: str, search_block: str, replace_block: str) -> Tuple[bool, str, Optional[str]]:
        return SmartPatcher.apply_search_replace(original_code, search_block, replace_block)


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
        span = SmartPatcher._fuzzy_find_block_span(source_lines, search_lines)
        return span[0] if span else None

    @staticmethod
    def _fuzzy_find_block_span(source_lines: List[str], search_lines: List[str]) -> Optional[Tuple[int, int]]:
        """Like fuzzy_find_block, but also returns the number of source lines
        actually consumed by the match (end - start), which mode 3 below can
        make differ from len(search_lines) by skipping extra blank lines --
        callers must splice using this count, not len(search_lines), or they
        drop or duplicate lines around the match."""
        if not search_lines or not source_lines:
            return None
        n_search = len(search_lines)
        if n_search > len(source_lines):
            return None

        # 1. Exact line match
        for i in range(len(source_lines) - n_search + 1):
            if source_lines[i:i + n_search] == search_lines:
                return (i, n_search)

        # 2. Strip trailing whitespace match
        clean_search = [line.rstrip() for line in search_lines]
        for i in range(len(source_lines) - n_search + 1):
            clean_source = [line.rstrip() for line in source_lines[i:i + n_search]]
            if clean_source == clean_search:
                return (i, n_search)

        # 3. Strip leading & trailing whitespace match (indentation-tolerant)
        trimmed_search = [line.strip() for line in search_lines if line.strip()]
        if not trimmed_search:
            return None

        for i in range(len(source_lines)):
            if source_lines[i].strip() == trimmed_search[0]:
                k = 0
                for j in range(i, min(len(source_lines), i + len(search_lines) + 10)):
                    src_blank = not source_lines[j].strip()
                    if src_blank:
                        # A blank source line always advances past -- it is
                        # either a real gap the search block also has (fine,
                        # trimmed_search skips blanks on both sides so there
                        # is nothing to compare here) or an extra blank the
                        # search doesn't have (also fine to skip over).
                        # Found by direct probe: the old version compared
                        # search_lines[k] -- indexed with k, an index into
                        # trimmed_search, not search_lines -- to decide
                        # whether to skip, which broke on the ordinary case
                        # of a blank line appearing at the same position in
                        # both source and search (it fell through to the
                        # match check, found "" != trimmed_search[k], and
                        # aborted the whole match).
                        continue
                    if k < len(trimmed_search) and source_lines[j].strip() == trimmed_search[k]:
                        k += 1
                        if k == len(trimmed_search):
                            # j is inclusive; the span is i..j, so its length
                            # is (j - i + 1) source lines -- may differ from
                            # n_search when blank lines were skipped over.
                            return (i, j - i + 1)
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

        span = SmartPatcher._fuzzy_find_block_span(orig_lines, search_lines)
        if span is not None:
            idx, consumed = span
            # A replace_block with no trailing newline (a model very
            # plausibly writes its replacement text without one) glues the
            # next source line onto the last replacement line once spliced
            # back in -- found by direct probe, pre-existing in this
            # function before this pass's other two fixes, not introduced
            # by them. Only append one when a real line still follows the
            # matched region, so a deliberate no-trailing-newline-at-EOF
            # replacement (the match genuinely is the last thing in the
            # file) is left untouched.
            if (replace_lines and not replace_lines[-1].endswith("\n")
                    and idx + consumed < len(orig_lines)):
                replace_lines[-1] += "\n"
            # Splice using `consumed`, the source lines the match actually
            # spans -- not len(search_lines). Mode 3 (indentation-tolerant)
            # can skip blank lines while matching, so those two counts can
            # differ; splicing with the wrong one silently drops or
            # duplicates a line adjacent to the match. Found by direct
            # probe: a search block spanning a blank line consumed 3 source
            # lines but len(search_lines) was also 3 in that case by
            # coincidence -- a search/source blank-line-count mismatch
            # would have made them diverge and corrupted the splice.
            matched_indent = orig_lines[idx][:len(orig_lines[idx]) - len(orig_lines[idx].lstrip(" \t"))]
            search_indent = search_lines[0][:len(search_lines[0]) - len(search_lines[0].lstrip(" \t"))]
            if matched_indent != search_indent:
                # The match only succeeded via mode 3's strip()-based
                # comparison, meaning indentation genuinely differs between
                # search and source. Re-apply the source's real indentation
                # to each replacement line instead of the caller's literal
                # leading whitespace -- found by direct probe: without this,
                # a tab-indented source patched with a 4-space search block
                # came back with the tab replaced by 4 literal spaces,
                # silently reformatting a line the caller never asked to
                # reformat.
                replace_lines = [
                    (matched_indent + line.lstrip(" \t")) if line.strip() else line
                    for line in replace_lines
                ]
            new_lines = orig_lines[:idx] + replace_lines + orig_lines[idx + consumed:]
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
            "lines_changed": len([line for line in diff.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))])
        }


# Global instance
codebase_indexer = CodebaseIndexer()
smart_patcher = SmartPatcher()



