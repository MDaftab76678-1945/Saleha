"""
Saleha Core: System-1 AST Scout & Call-Chain Localizer (Zero-Token Navigation).

Provides deterministic, sub-50ms static symbol localization, multi-hop BFS
call-chain extraction (caller -> callee levels), and test file association
before invoking LLM reasoning.

Addresses the Pass 106 SWE-bench navigation/depth gap where models patch one level
too shallow by surfacing callee helper definitions and exact line slices upfront.
"""



from __future__ import annotations

import os
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple

from saleha.core.graph.codebase_indexer import (
    ClassSymbol,
    CodebaseIndexer,
    FileIndex,
    FunctionSymbol,
)
from saleha.core.graph.dependency_graph import CodebaseDependencyGraph

_STOP_WORDS: Set[str] = {
    "def", "class", "import", "from", "return", "pass", "raise", "try", "except",
    "finally", "while", "for", "in", "if", "elif", "else", "with", "as", "assert",
    "async", "await", "yield", "none", "true", "false", "and", "or", "not", "is",
    "self", "cls", "test", "tests", "file", "files", "error", "failed", "passed",
    "traceback", "line", "module", "package", "repo", "repository", "code", "bug",
    "fix", "repair", "patch", "issue", "problem", "solve", "failing", "pytest",
    "unit", "integration", "asserts", "assertion", "expected", "actual", "call",
    "called", "calling", "calls", "using", "make", "sure", "check", "need",
    "should", "could", "would", "the", "a", "an", "this", "that", "these", "those",
    "when", "where", "why", "how", "what", "which", "who", "whom", "whose",
    "into", "onto", "about", "after", "before", "during", "through", "over", "under",
    "to", "of", "by", "at", "on", "up", "do", "it", "so", "be", "no", "my", "we", "he",
}

_BUILTIN_CALLS: Set[str] = {
    "len", "print", "isinstance", "issubclass", "getattr", "setattr", "hasattr",
    "delattr", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
    "open", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "min", "max", "sum", "any", "all", "id", "type", "repr", "super", "object",
    "format", "round", "abs", "iter", "next", "callable", "bytes", "bytearray",
}


def _is_test_path(rel_path: str) -> bool:
    """Returns True if the path represents a unit or integration test."""
    norm = (rel_path or "").replace("\\", "/").lower()
    name = norm.rsplit("/", 1)[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
        or "/tests/" in norm
        or norm.startswith("tests/")
        or "/test/" in norm
        or norm.startswith("test/")
    )


@dataclass
class SymbolDossier:
    """Detailed structural record for a localized symbol."""

    name: str
    kind: str  # 'function', 'class', 'method'
    file_path: str
    start_line: int
    end_line: int
    docstring: str = ""
    code_slice: str = ""
    callees: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)
    parent_class: Optional[str] = None


@dataclass
class ScoutDossier:
    """Complete System-1 pre-flight reconnaissance briefing."""

    query: str
    primary_symbols: List[SymbolDossier] = field(default_factory=list)
    callee_symbols: List[SymbolDossier] = field(default_factory=list)
    relevant_files: Set[str] = field(default_factory=set)
    test_files: List[str] = field(default_factory=list)
    primary_region: Optional[Tuple[str, int, int]] = None

    @property
    def has_matches(self) -> bool:
        """True if any primary symbols or callee definitions were resolved."""
        return bool(self.primary_symbols or self.callee_symbols)

    def format_briefing(self, max_chars: int = 1200) -> str:
        """Formats a concise markdown dossier for prompt injection."""
        if not self.has_matches:
            return ""

        sections: List[str] = ["[System-1 Scout Localization]"]

        # Primary Symbols
        for sym in self.primary_symbols[:2]:
            display = f"`{sym.name}`"
            if sym.parent_class:
                display = f"`{sym.parent_class}.{sym.name}`"
            sections.append(f"Target Symbol: {display} in `{sym.file_path}` (lines {sym.start_line}-{sym.end_line})")

        # Callee helpers (Addresses Pass 106 one-level-shallow bug)
        if self.callee_symbols:
            callee_items: List[str] = []
            for c in self.callee_symbols[:4]:
                callee_items.append(f"`{c.name}` in `{c.file_path}:{c.start_line}`")
            sections.append("Callees (Helpers called inside target): " + ", ".join(callee_items))

        # Test references
        if self.test_files:
            sections.append("Associated Tests: " + ", ".join(f"`{t}`" for t in self.test_files[:3]))

        # Code Slices
        sections.append("Extracted Code Slices:")
        for sym in (self.primary_symbols[:1] + self.callee_symbols[:2]):
            if sym.code_slice:
                sections.append(f"--- {sym.file_path} (lines {sym.start_line}-{sym.end_line}) ---\n{sym.code_slice}")

        briefing = "\n".join(sections)
        if len(briefing) > max_chars:
            briefing = briefing[:max_chars] + "\n...[scout briefing truncated]"
        return briefing


class System1Scout:
    """
    Fast, deterministic AST-based symbol locator and call-chain scout.
    Runs locally in under 50ms without invoking LLM tokens.
    """

    def __init__(self, root_dir: str = ".") -> None:
        self.root_dir = os.path.abspath(root_dir)
        self._indexer = CodebaseIndexer(root_dir=self.root_dir)
        self._dep_graph = CodebaseDependencyGraph(root_dir=self.root_dir)

    def extract_candidates(self, text: str) -> List[str]:
        """Extracts candidate symbol identifiers from a goal string or traceback."""
        if not text:
            return []

        # Split on whitespace, punctuation, slashes, dots, and colons
        raw_tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text)
        candidates: List[str] = []
        seen: Set[str] = set()

        for tok in raw_tokens:
            low = tok.lower()
            if low in _STOP_WORDS:
                continue
            if tok not in seen:
                seen.add(tok)
                candidates.append(tok)

        return candidates

    def _read_code_slice(self, rel_path: str, start_line: int, end_line: int, max_lines: int = 35) -> str:
        """Reads a numbered slice of code from the workspace with strict boundary clamping."""
        abs_p = os.path.abspath(os.path.join(self.root_dir, rel_path))
        if not os.path.isfile(abs_p) or start_line <= 0:
            return ""

        effective_end = max(start_line, end_line)
        bound_end = min(effective_end, start_line + max_lines)
        lines_out: List[str] = []

        try:
            with open(abs_p, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f, 1):
                    if idx > bound_end:
                        break
                    if idx >= start_line:
                        lines_out.append(f"{idx}: {line.rstrip()}")
            if effective_end > bound_end:
                lines_out.append("... [body continues]")
            return "\n".join(lines_out)
        except OSError:
            return ""

    def _lookup_function_or_method(
        self, file_idx: FileIndex, name: str
    ) -> Tuple[Optional[FunctionSymbol], Optional[str]]:
        """Finds a top-level function or class method in an indexed file."""
        if name in file_idx.functions:
            return file_idx.functions[name], None
        for c_name, c_def in file_idx.classes.items():
            if name in c_def.methods:
                return c_def.methods[name], c_name
        return None, None

    def _record_primary_symbol(
        self,
        cand: str,
        rel_file: str,
        file_idx: FileIndex,
        dossier: ScoutDossier,
    ) -> bool:
        """Inspects file_idx for candidate symbol and appends to dossier if found."""
        fn_sym, parent_cls_name = self._lookup_function_or_method(file_idx, cand)
        if fn_sym:
            code_slice = self._read_code_slice(rel_file, fn_sym.start_line, fn_sym.end_line)
            sym_dossier = SymbolDossier(
                name=cand,
                kind="method" if parent_cls_name else "function",
                file_path=rel_file,
                start_line=fn_sym.start_line,
                end_line=fn_sym.end_line,
                docstring=fn_sym.docstring or "",
                code_slice=code_slice,
                callees=fn_sym.calls,
                parent_class=parent_cls_name,
            )
            dossier.primary_symbols.append(sym_dossier)
            dossier.relevant_files.add(rel_file)
            if dossier.primary_region is None:
                dossier.primary_region = (rel_file, fn_sym.start_line, fn_sym.end_line)
            return True

        cls_sym: Optional[ClassSymbol] = file_idx.classes.get(cand)
        if cls_sym:
            code_slice = self._read_code_slice(rel_file, cls_sym.start_line, cls_sym.end_line, max_lines=20)
            sym_dossier = SymbolDossier(
                name=cand,
                kind="class",
                file_path=rel_file,
                start_line=cls_sym.start_line,
                end_line=cls_sym.end_line,
                docstring=cls_sym.docstring or "",
                code_slice=code_slice,
            )
            dossier.primary_symbols.append(sym_dossier)
            dossier.relevant_files.add(rel_file)
            if dossier.primary_region is None:
                dossier.primary_region = (rel_file, cls_sym.start_line, cls_sym.end_line)
            return True

        return False

    def _resolve_primary_symbols(
        self,
        candidates: List[str],
        files_indexed: Dict[str, FileIndex],
        dossier: ScoutDossier,
    ) -> Set[str]:
        """Resolves primary candidate symbols from candidate tokens."""
        resolved: Set[str] = set()

        for cand in candidates:
            if cand in resolved:
                continue

            for rel_file in self._indexer.find_symbol(cand):
                file_idx = files_indexed.get(rel_file)
                if file_idx and self._record_primary_symbol(cand, rel_file, file_idx, dossier):
                    resolved.add(cand)
                    break

        return resolved


    def _record_callee_if_found(
        self,
        callee_name: str,
        callee_file: str,
        cf_idx: FileIndex,
        dossier: ScoutDossier,
    ) -> Optional[SymbolDossier]:
        """Creates and appends a callee SymbolDossier if resolved in cf_idx."""
        c_fn, c_parent = self._lookup_function_or_method(cf_idx, callee_name)
        if not c_fn:
            return None

        c_slice = self._read_code_slice(callee_file, c_fn.start_line, c_fn.end_line)
        callee_dossier = SymbolDossier(
            name=callee_name,
            kind="method" if c_parent else "function",
            file_path=callee_file,
            start_line=c_fn.start_line,
            end_line=c_fn.end_line,
            docstring=c_fn.docstring or "",
            code_slice=c_slice,
            callees=c_fn.calls,
            parent_class=c_parent,
        )
        dossier.callee_symbols.append(callee_dossier)
        dossier.relevant_files.add(callee_file)
        return callee_dossier

    def _resolve_callees_bfs(
        self,
        max_depth: int,
        files_indexed: Dict[str, FileIndex],
        dossier: ScoutDossier,
        resolved_primaries: Set[str],
    ) -> Set[str]:
        """Resolves callees via multi-hop BFS queue traversal."""
        resolved_callees: Set[str] = set()
        queue: Deque[Tuple[SymbolDossier, int]] = deque((s, 1) for s in dossier.primary_symbols)

        while queue:
            current_sym, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for callee_name in current_sym.callees:
                if (
                    callee_name in _BUILTIN_CALLS
                    or callee_name in resolved_primaries
                    or callee_name in resolved_callees
                ):
                    continue

                for callee_file in self._indexer.find_symbol(callee_name):
                    cf_idx = files_indexed.get(callee_file)
                    if not cf_idx:
                        continue

                    callee_dossier = self._record_callee_if_found(callee_name, callee_file, cf_idx, dossier)
                    if callee_dossier:
                        resolved_callees.add(callee_name)
                        queue.append((callee_dossier, depth + 1))
                        break

        return resolved_callees

    def _match_test_files(
        self,
        files_indexed: Dict[str, FileIndex],
        target_names: Set[str],
        dossier: ScoutDossier,
        candidates: Optional[List[str]] = None,
    ) -> None:
        """Associates workspace test files via AST symbols, called functions, and imports."""
        target_names_lower = {t.lower() for t in target_names}
        candidate_tokens_lower = {c.lower() for c in (candidates or []) if len(c) >= 3}
        search_tokens = target_names_lower | candidate_tokens_lower

        for rel_path, file_idx in files_indexed.items():
            if not _is_test_path(rel_path):
                continue

            all_fns: List[FunctionSymbol] = list(file_idx.functions.values())
            for cls_sym in file_idx.classes.values():
                all_fns.extend(cls_sym.methods.values())

            # 1. Match on test function or class method names
            matched = any(
                any(t_name in fn.name.lower() for t_name in search_tokens)
                for fn in all_fns
            )

            # 2. Match on calls made inside test functions (e.g. test calls iter_content)
            if not matched:
                matched = any(
                    any(t_name in c.lower() for t_name in target_names_lower)
                    for fn in all_fns
                    for c in fn.calls
                )

            # 3. Match on imports in test file
            if not matched:
                matched = any(
                    any(t_name in imp for t_name in target_names)
                    for imp in file_idx.imports
                )

            # 4. Match on from_imports in test file
            if not matched:
                matched = any(
                    any(t_name in from_mod or t_name in from_names for t_name in target_names)
                    for from_mod, from_names in file_idx.from_imports.items()
                )

            if matched:
                dossier.test_files.append(rel_path)
                dossier.relevant_files.add(rel_path)

    def scout(self, goal: str, max_depth: int = 2) -> ScoutDossier:
        """Performs static reconnaissance to locate symbols, callees, and test files."""
        candidates = self.extract_candidates(goal)
        dossier = ScoutDossier(query=goal)

        if not candidates:
            return dossier

        files_indexed = self._indexer.scan()
        self._dep_graph.build_graph()

        resolved_primaries = self._resolve_primary_symbols(candidates, files_indexed, dossier)
        resolved_callees = self._resolve_callees_bfs(max_depth, files_indexed, dossier, resolved_primaries)
        target_names = {s.name for s in dossier.primary_symbols} | resolved_callees
        self._match_test_files(files_indexed, target_names, dossier, candidates=candidates)

        return dossier


system1_scout = System1Scout()

__all__ = [
    "SymbolDossier",
    "ScoutDossier",
    "System1Scout",
    "system1_scout",
]
