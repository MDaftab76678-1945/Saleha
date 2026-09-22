#!/usr/bin/env python3
"""Context Compaction & Token Budget Optimizer for 3B/8B Local Models.

Prunes non-essential code blocks, comments, and docstrings while preserving
syntactic validity and semantic symbols to fit within strict token boundaries.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any


def strip_docstrings_and_comments(source_code: str) -> str:
    """Parses source AST and removes docstrings, returning compacted source."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # Fallback to basic line-by-line comment stripper if syntax error exists
        lines = []
        for line in source_code.splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                lines.append(line)
        return "\n".join(lines)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                # Replace docstring with pass if it's the sole statement, otherwise remove
                if len(node.body) == 1:
                    node.body[0] = ast.Pass()
                else:
                    node.body.pop(0)

    try:
        return ast.unparse(tree)
    except Exception:
        return source_code


def extract_code_skeleton(source_code: str) -> str:
    """Generates an interface skeleton with function/class signatures and type annotations."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Replace function body with pass
            node.body = [ast.Pass()]
        elif isinstance(node, ast.ClassDef):
            # Keep class attributes or methods but stub method bodies
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item.body = [ast.Pass()]

    try:
        return ast.unparse(tree)
    except Exception:
        return source_code


def compact_file_to_budget(
    file_path: Path,
    max_tokens: int = 1500,
    query: Optional[str] = None,
    skeleton_mode: bool = False,
) -> Dict[str, Any]:
    """Compacts the file content according to budget constraints."""
    if not file_path.exists():
        return {"error": f"File not found: {file_path}", "status": "failed"}

    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    original_chars = len(raw_text)
    # Estimate tokens: approx 4 characters per token
    char_budget = max_tokens * 4

    if skeleton_mode:
        compacted = extract_code_skeleton(raw_text)
    else:
        compacted = strip_docstrings_and_comments(raw_text)

    # If still over budget and query provided, extract focus region
    if len(compacted) > char_budget and query:
        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        lines = compacted.splitlines()
        scored_lines: List[tuple[int, str, int]] = []

        for idx, line in enumerate(lines):
            score = sum(line.lower().count(term) for term in query_terms)
            scored_lines.append((idx, line, score))

        # Sort by relevance and take context windows
        best_indices = sorted(
            [idx for idx, _, score in scored_lines if score > 0],
            key=lambda i: scored_lines[i][2],
            reverse=True,
        )

        if best_indices:
            selected_lines_set = set()
            for center in best_indices[:10]:
                for offset in range(-5, 6):
                    cur = center + offset
                    if 0 <= cur < len(lines):
                        selected_lines_set.add(cur)
            ordered_indices = sorted(selected_lines_set)
            compacted = "\n".join(lines[i] for i in ordered_indices)

    if len(compacted) > char_budget:
        compacted = compacted[:char_budget] + "\n# [TRUNCATED DUE TO COGNITIVE BUDGET]"

    compacted_chars = len(compacted)
    compression_ratio = (
        (1.0 - (compacted_chars / original_chars)) * 100.0 if original_chars > 0 else 0.0
    )

    return {
        "status": "success",
        "file": str(file_path),
        "original_chars": original_chars,
        "compacted_chars": compacted_chars,
        "estimated_tokens": compacted_chars // 4,
        "compression_percent": round(compression_ratio, 2),
        "content": compacted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compact Python source code to fit strict LLM token budgets."
    )
    parser.add_argument("--file", "-f", required=True, help="Path to Python file to compact.")
    parser.add_argument(
        "--budget", "-b", type=int, default=1500, help="Maximum token budget (default: 1500)."
    )
    parser.add_argument("--query", "-q", type=str, default=None, help="Optional focus query terms.")
    parser.add_argument(
        "--skeleton", "-s", action="store_true", help="Generate signature-only skeleton."
    )
    parser.add_argument("--output", "-o", type=str, default=None, help="Optional output file path.")

    args = parser.parse_args()
    target_path = Path(args.file)
    result = compact_file_to_budget(
        file_path=target_path,
        max_tokens=args.budget,
        query=args.query,
        skeleton_mode=args.skeleton,
    )

    if result.get("status") != "success":
        sys.stderr.write(f"Error: {result.get('error')}\n")
        return 1

    content = result["content"]
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(
            f"Wrote compacted content ({result['estimated_tokens']} tokens, {result['compression_percent']}% reduced) to: {out_path}"
        )
    else:
        print(content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
