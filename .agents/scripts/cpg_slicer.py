#!/usr/bin/env python3
"""Code Property Graph (CPG) Backward Program Slicer.

Extracts minimal causal code slices based on AST, Control-Flow, and Data-Flow
dependencies. Eliminates irrelevant code to feed dense, zero-noise context to
local 3B/8B coder models.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Any, Optional


class DefUseCollector(ast.NodeVisitor):
    """Collects variable definitions and usages per statement line."""

    def __init__(self) -> None:
        self.line_defs: Dict[int, Set[str]] = {}
        self.line_uses: Dict[int, Set[str]] = {}
        self.control_deps: Dict[int, Set[int]] = {}
        self._current_control_stack: List[int] = []

    def _record_def(self, line: int, var_name: str) -> None:
        self.line_defs.setdefault(line, set()).add(var_name)
        if self._current_control_stack:
            self.control_deps.setdefault(line, set()).update(self._current_control_stack)

    def _record_use(self, line: int, var_name: str) -> None:
        self.line_uses.setdefault(line, set()).add(var_name)
        if self._current_control_stack:
            self.control_deps.setdefault(line, set()).update(self._current_control_stack)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        line = node.lineno
        self._record_def(line, node.name)
        # Function arguments are definitions at function line
        for arg in node.args.args:
            self._record_def(line, arg.arg)
        if node.args.vararg:
            self._record_def(line, node.args.vararg.arg)
        if node.args.kwarg:
            self._record_def(line, node.args.kwarg.arg)

        self._current_control_stack.append(line)
        self.generic_visit(node)
        self._current_control_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_If(self, node: ast.If) -> None:
        line = node.lineno
        # Condition variables are used at the If line
        for child in ast.walk(node.test):
            if isinstance(child, ast.Name):
                self._record_use(line, child.id)

        self._current_control_stack.append(line)
        self.generic_visit(node)
        self._current_control_stack.pop()

    def visit_While(self, node: ast.While) -> None:
        line = node.lineno
        for child in ast.walk(node.test):
            if isinstance(child, ast.Name):
                self._record_use(line, child.id)
        self._current_control_stack.append(line)
        self.generic_visit(node)
        self._current_control_stack.pop()

    def visit_For(self, node: ast.For) -> None:
        line = node.lineno
        # Target variables defined in For loop header
        for child in ast.walk(node.target):
            if isinstance(child, ast.Name):
                self._record_def(line, child.id)
        for child in ast.walk(node.iter):
            if isinstance(child, ast.Name):
                self._record_use(line, child.id)

        self._current_control_stack.append(line)
        self.generic_visit(node)
        self._current_control_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        line = node.lineno
        for target in node.targets:
            for child in ast.walk(target):
                if isinstance(child, ast.Name):
                    self._record_def(line, child.id)
        for child in ast.walk(node.value):
            if isinstance(child, ast.Name):
                self._record_use(line, child.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        line = node.lineno
        if isinstance(node.target, ast.Name):
            self._record_def(line, node.target.id)
        if node.value:
            for child in ast.walk(node.value):
                if isinstance(child, ast.Name):
                    self._record_use(line, child.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        line = node.lineno
        if isinstance(node.target, ast.Name):
            self._record_def(line, node.target.id)
            self._record_use(line, node.target.id)
        for child in ast.walk(node.value):
            if isinstance(child, ast.Name):
                self._record_use(line, child.id)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        line = node.lineno
        if node.value:
            for child in ast.walk(node.value):
                if isinstance(child, ast.Name):
                    self._record_use(line, child.id)
        self.generic_visit(node)


def compute_backward_slice(
    source_code: str,
    target_line: int,
    target_var: Optional[str] = None,
) -> Dict[str, Any]:
    """Computes static backward program slice for a given line or variable."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return {"status": "error", "message": f"Syntax error during slice: {e}"}

    collector = DefUseCollector()
    collector.visit(tree)

    # Initialize slicing criterion
    active_vars: Set[str] = set()
    if target_var:
        active_vars.add(target_var)
    elif target_line in collector.line_uses:
        active_vars.update(collector.line_uses[target_line])
    elif target_line in collector.line_defs:
        active_vars.update(collector.line_defs[target_line])

    sliced_lines: Set[int] = {target_line}
    worklist: List[int] = [target_line]
    visited: Set[int] = set()

    # Traverse backwards from target line
    all_lines = sorted(set(collector.line_defs.keys()) | set(collector.line_uses.keys()), reverse=True)

    while worklist or active_vars:
        current_line = worklist.pop(0) if worklist else None
        progress = False

        for line in all_lines:
            if line in visited or (current_line and line >= current_line):
                continue

            defs = collector.line_defs.get(line, set())
            # Data dependency: Does this line define a variable we need?
            overlap = defs.intersection(active_vars)
            if overlap:
                sliced_lines.add(line)
                visited.add(line)
                progress = True
                # Add new variables used by this defining statement
                active_vars.update(collector.line_uses.get(line, set()))
                # Add control dependencies (e.g. enclosing If/For)
                for ctrl_line in collector.control_deps.get(line, set()):
                    sliced_lines.add(ctrl_line)
                    worklist.append(ctrl_line)

        if not progress:
            break

    raw_lines = source_code.splitlines()
    sorted_sliced_lines = sorted(sliced_lines)
    result_lines = []
    for line_no in sorted_sliced_lines:
        if 1 <= line_no <= len(raw_lines):
            result_lines.append(f"{line_no:4d}: {raw_lines[line_no - 1]}")

    reduction = (
        (1.0 - (len(sorted_sliced_lines) / max(len(raw_lines), 1))) * 100.0
    )

    return {
        "status": "success",
        "target_line": target_line,
        "total_source_lines": len(raw_lines),
        "sliced_lines_count": len(sorted_sliced_lines),
        "reduction_percent": round(reduction, 2),
        "sliced_code": "\n".join(result_lines),
        "line_indices": sorted_sliced_lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute static backward slice of a Python file for targeted LLM context."
    )
    parser.add_argument("--file", "-f", required=True, help="Path to Python file.")
    parser.add_argument("--line", "-l", type=int, required=True, help="Target line number.")
    parser.add_argument("--var", "-v", type=str, default=None, help="Target variable name.")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output destination file.")

    args = parser.parse_args()
    file_path = Path(args.file)
    if not file_path.exists():
        sys.stderr.write(f"File not found: {file_path}\n")
        return 1

    source_code = file_path.read_text(encoding="utf-8", errors="replace")
    res = compute_backward_slice(source_code, args.line, args.var)

    if res.get("status") != "success":
        sys.stderr.write(f"Error: {res.get('message')}\n")
        return 1

    output_str = res["sliced_code"]
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Slice ({res['sliced_lines_count']} lines, {res['reduction_percent']}% reduction) saved to: {out_path}")
    else:
        print(f"# Backward Slice for {file_path.name}:{args.line} ({res['reduction_percent']}% reduction)")
        print(output_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
