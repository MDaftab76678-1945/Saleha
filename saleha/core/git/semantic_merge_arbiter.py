"""Saleha Core: Semantic 3-Way Git Merge Conflict Arbiter.

Performs AST-aware 3-way merge conflict resolution. Distinguishes between
benign adjacent symbol additions (merging distinct functions cleanly) and
genuine statement contradictions, validating the resulting AST before ratifying.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ConflictHunk:
    """Represents a single Git conflict block."""
    hunk_id: int
    ours_content: str
    theirs_content: str
    base_content: Optional[str] = None
    ours_label: str = "HEAD"
    theirs_label: str = "incoming"


@dataclass
class SemanticMergeResult:
    """Authoritative outcome of a semantic merge operation."""
    file_path: str
    total_conflicts: int
    resolved_conflicts: int
    unresolved_conflicts: int
    is_valid_ast: bool
    status: str  # "CLEAN_RESOLVED", "PARTIAL_RESOLVED", "MANUAL_REQUIRED"
    resolved_code: str
    summary: str


class SemanticMergeArbiter:
    """AST-driven Git merge conflict resolver."""

    # Matches 2-way and 3-way conflict markers
    CONFLICT_REGEX = re.compile(
        r"^<{7}[ \t]*(.*?)\n(.*?)(?:\|{7}[ \t]*(.*?)\n(.*?))?={7}\n(.*?)>{7}[ \t]*([^\n]*)(?:\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    def __init__(self) -> None:
        pass

    def extract_conflict_hunks(self, content: str) -> List[ConflictHunk]:
        """Parses git conflict markers into discrete ConflictHunk instances."""
        hunks: List[ConflictHunk] = []
        for i, m in enumerate(self.CONFLICT_REGEX.finditer(content), 1):
            ours_lbl = m.group(1).strip() or "HEAD"
            ours_txt = m.group(2)
            base_txt = m.group(4) if m.group(3) else None
            theirs_txt = m.group(5)
            theirs_lbl = m.group(6).strip() or "incoming"

            hunks.append(
                ConflictHunk(
                    hunk_id=i,
                    ours_content=ours_txt,
                    theirs_content=theirs_txt,
                    base_content=base_txt,
                    ours_label=ours_lbl,
                    theirs_label=theirs_lbl,
                )
            )
        return hunks

    def _attempt_ast_symbol_union(self, ours_code: str, theirs_code: str) -> Optional[str]:
        """Attempts to cleanly union distinct AST symbols added by both branches."""
        try:
            tree_ours = ast.parse(ours_code)
            tree_theirs = ast.parse(theirs_code)
        except SyntaxError:
            return None

        ours_symbols: Dict[str, ast.AST] = {}
        theirs_symbols: Dict[str, ast.AST] = {}

        # Any other statement (assignment, call, if ...) that differs between the
        # sides is a real contradiction; a union would silently keep both.
        def _other_stmts(tree: ast.Module) -> List[str]:
            return [
                ast.unparse(n) for n in tree.body
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))
            ]

        if _other_stmts(tree_ours) != _other_stmts(tree_theirs):
            return None

        for n in tree_ours.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                ours_symbols[n.name] = n
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                ours_symbols[ast.unparse(n)] = n

        for n in tree_theirs.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                theirs_symbols[n.name] = n
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                theirs_symbols[ast.unparse(n)] = n

        # Check if symbol names are completely distinct (benign collision on adjacent lines)
        common_symbols = set(ours_symbols.keys()) & set(theirs_symbols.keys())

        if not common_symbols and (ours_symbols or theirs_symbols):
            # Union all nodes without duplicate imports
            combined_body: List[ast.stmt] = []
            seen_unparsed = set()

            for n in list(tree_ours.body) + list(tree_theirs.body):
                unp = ast.unparse(n)
                if unp not in seen_unparsed:
                    seen_unparsed.add(unp)
                    combined_body.append(n)

            module_node = ast.Module(body=combined_body, type_ignores=[])
            return ast.unparse(module_node)

        # If identical content
        if ours_code.strip() == theirs_code.strip():
            return ours_code.strip()

        return None

    def resolve_conflicted_content(
        self,
        content: str,
        file_path: str = "conflicted_file.py",
    ) -> SemanticMergeResult:
        """Resolves all git conflict blocks in content using AST semantic arbitration."""
        hunks = self.extract_conflict_hunks(content)
        if not hunks:
            try:
                ast.parse(content)
                is_ast = True
            except SyntaxError:
                is_ast = False

            return SemanticMergeResult(
                file_path=file_path,
                total_conflicts=0,
                resolved_conflicts=0,
                unresolved_conflicts=0,
                is_valid_ast=is_ast,
                status="CLEAN_RESOLVED",
                resolved_code=content,
                summary="No Git conflict markers present in file.",
            )

        resolved_count = 0
        unresolved_count = 0

        # Replace each conflict hunk in order
        def _replace_hunk(match: re.Match) -> str:
            nonlocal resolved_count, unresolved_count
            ours_txt = match.group(2)
            theirs_txt = match.group(5)

            union = self._attempt_ast_symbol_union(ours_txt, theirs_txt)
            if union is not None:
                resolved_count += 1
                return union + "\n"
            else:
                unresolved_count += 1
                # Preserve hunk for manual inspection if impossible to resolve cleanly
                return match.group(0)

        merged_code = self.CONFLICT_REGEX.sub(_replace_hunk, content)

        # Verify AST validity of the resulting file
        is_ast_valid = False
        try:
            ast.parse(merged_code)
            is_ast_valid = True
        except SyntaxError:
            is_ast_valid = False

        if unresolved_count == 0 and is_ast_valid:
            status = "CLEAN_RESOLVED"
        elif resolved_count > 0:
            status = "PARTIAL_RESOLVED"
        else:
            status = "MANUAL_REQUIRED"

        summary = (
            f"Semantic Merge: {status}. Total hunks: {len(hunks)}, "
            f"Resolved: {resolved_count}, Unresolved: {unresolved_count}. AST Valid: {is_ast_valid}."
        )

        return SemanticMergeResult(
            file_path=file_path,
            total_conflicts=len(hunks),
            resolved_conflicts=resolved_count,
            unresolved_conflicts=unresolved_count,
            is_valid_ast=is_ast_valid,
            status=status,
            resolved_code=merged_code,
            summary=summary,
        )
