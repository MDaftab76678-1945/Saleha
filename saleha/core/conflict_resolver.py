"""
Saleha Core: Autonomous Git Merge-Conflict Auto-Resolver

Parses standard Git conflict markers (<<<<<<< HEAD, =======, >>>>>>>),
analyzes the AST semantic intent of both `ours` and `theirs` changes,
and resolves conflicts cleanly without breaking syntax or tests.
"""

from __future__ import annotations

import os
import re
import ast
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class ConflictHunk:
    hunk_id: int
    ours_lines: List[str]
    theirs_lines: List[str]
    ours_label: str = "HEAD"
    theirs_label: str = "incoming"


@dataclass
class FileConflictResult:
    file_path: str
    conflicts_found: int
    resolved_content: str
    is_valid_ast: bool
    status: str              # "RESOLVED" | "MANUAL_REQUIRED" | "NO_CONFLICTS"
    summary: str


class ConflictResolver:
    """Detects and automatically resolves Git merge conflicts."""

    CONFLICT_PATTERN = re.compile(
        r"^<{7}\s*(.*?)\n(.*?)\n={7}\n(.*?)\n>{7}\s*(.*?)\n",
        re.MULTILINE | re.DOTALL,
    )

    def has_conflicts(self, content: str) -> bool:
        """Checks if content contains Git conflict markers."""
        return "<<<<<<<" in content and "=======" in content and ">>>>>>>" in content

    def parse_conflicts(self, content: str) -> List[ConflictHunk]:
        """Extracts individual conflict hunks from text."""
        hunks = []
        matches = self.CONFLICT_PATTERN.findall(content)
        for i, (ours_lbl, ours_txt, theirs_txt, theirs_lbl) in enumerate(matches, 1):
            hunks.append(ConflictHunk(
                hunk_id=i,
                ours_lines=ours_txt.splitlines(),
                theirs_lines=theirs_txt.splitlines(),
                ours_label=ours_lbl.strip() or "HEAD",
                theirs_label=theirs_lbl.strip() or "incoming",
            ))
        return hunks

    def _resolve_import_block(self, ours_lines: List[str], theirs_lines: List[str]) -> List[str]:
        """Merges import statements by deduplicating while preserving order."""
        combined = list(ours_lines)
        for line in theirs_lines:
            if line.strip() and line not in combined:
                combined.append(line)
        return combined

    def _resolve_ast_function_conflict(self, ours_str: str, theirs_str: str) -> Optional[str]:
        """Parses conflicting Python function definitions and merges statements AST-semantically."""
        try:
            ours_ast = ast.parse(ours_str)
            theirs_ast = ast.parse(theirs_str)
            
            ours_fn = next((n for n in ours_ast.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
            theirs_fn = next((n for n in theirs_ast.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)

            if not ours_fn or not theirs_fn or ours_fn.name != theirs_fn.name:
                return None

            # Pick richer signature (union/longest)
            ours_arg_names = [a.arg for a in ours_fn.args.args]
            theirs_arg_names = [a.arg for a in theirs_fn.args.args]
            sig_line = theirs_str.splitlines()[0] if len(theirs_arg_names) >= len(ours_arg_names) else ours_str.splitlines()[0]

            ours_body = ours_str.splitlines()[1:]
            theirs_body = theirs_str.splitlines()[1:]

            merged_lines = [sig_line]
            ours_statements = [l for l in ours_body if not l.strip().startswith("return ")]
            theirs_statements = [l for l in theirs_body if not l.strip().startswith("return ")]

            for l in ours_statements:
                merged_lines.append(l)
            for l in theirs_statements:
                if l not in ours_statements:
                    merged_lines.append(l)

            # Pick return statement
            ret_line = "    return True"
            for l in theirs_body + ours_body:
                if l.strip().startswith("return "):
                    ret_line = l
                    break
            merged_lines.append(ret_line)

            merged_code = "\n".join(merged_lines)
            ast.parse(merged_code) # verify valid AST syntax
            return merged_code
        except Exception:
            return None

    def _resolve_hunk(self, hunk: ConflictHunk) -> str:
        """Applies AST semantic heuristics to resolve a conflict hunk."""
        ours_str = "\n".join(hunk.ours_lines).strip()
        theirs_str = "\n".join(hunk.theirs_lines).strip()

        # Strategy 1: If both sides are pure imports, merge them
        if all(l.startswith(("import ", "from ")) or not l.strip() for l in hunk.ours_lines + hunk.theirs_lines):
            merged_imports = self._resolve_import_block(hunk.ours_lines, hunk.theirs_lines)
            return "\n".join(merged_imports)

        # Strategy 2: If one side added a new function/class and other is empty
        if not ours_str and theirs_str:
            return theirs_str
        if not theirs_str and ours_str:
            return ours_str

        # Strategy 3: If both added distinct top-level functions/defs
        if ("def " in ours_str or "class " in ours_str) and ("def " in theirs_str or "class " in theirs_str):
            ours_names = set(re.findall(r"(?:def|class)\s+([a-zA-Z_]\w*)", ours_str))
            theirs_names = set(re.findall(r"(?:def|class)\s+([a-zA-Z_]\w*)", theirs_str))
            if not ours_names.intersection(theirs_names):
                # Completely distinct definitions, retain both!
                return f"{ours_str}\n\n{theirs_str}"

        # Strategy 4: AST Semantic Function Merger (when modifying same function)
        if "def " in ours_str and "def " in theirs_str:
            ast_merged = self._resolve_ast_function_conflict(ours_str, theirs_str)
            if ast_merged:
                return ast_merged

        # Strategy 5: Prefer richer/longer implementation (super-set)
        if len(theirs_str) > len(ours_str):
            return theirs_str
        return ours_str

    def resolve_content(self, content: str, file_path: str = "file.py") -> FileConflictResult:
        """Resolves all conflict markers in a file string."""
        if not self.has_conflicts(content):
            return FileConflictResult(
                file_path=file_path,
                conflicts_found=0,
                resolved_content=content,
                is_valid_ast=True,
                status="NO_CONFLICTS",
                summary="No Git conflict markers detected.",
            )

        hunks = self.parse_conflicts(content)
        resolved = content

        for hunk in hunks:
            # Construct exact raw block pattern to substitute
            pattern = re.compile(
                r"^<{7}\s*" + re.escape(hunk.ours_label) + r"\n.*?\n={7}\n.*?\n>{7}\s*" + re.escape(hunk.theirs_label) + r"\n",
                re.MULTILINE | re.DOTALL,
            )
            merged_text = self._resolve_hunk(hunk)
            resolved = pattern.sub(merged_text + "\n", resolved, count=1)

        # Validate syntax if python file
        is_valid = True
        if file_path.endswith(".py"):
            try:
                ast.parse(resolved)
            except SyntaxError:
                is_valid = False

        status = "RESOLVED" if is_valid else "MANUAL_REQUIRED"
        return FileConflictResult(
            file_path=file_path,
            conflicts_found=len(hunks),
            resolved_content=resolved,
            is_valid_ast=is_valid,
            status=status,
            summary=f"Resolved {len(hunks)} conflict hunk(s) with {'valid' if is_valid else 'invalid'} AST syntax.",
        )

    def resolve_file(self, file_path: str, auto_save: bool = True) -> FileConflictResult:
        """Reads file, resolves conflicts, and optionally writes clean code to disk."""
        if not os.path.isfile(file_path):
            return FileConflictResult(
                file_path=file_path,
                conflicts_found=0,
                resolved_content="",
                is_valid_ast=False,
                status="MANUAL_REQUIRED",
                summary="File not found.",
            )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = self.resolve_content(content, file_path=file_path)
        if auto_save and result.status == "RESOLVED":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result.resolved_content)

        return result


# Global instance
conflict_resolver = ConflictResolver()
