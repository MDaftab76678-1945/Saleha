"""Saleha Core: Code Property Graph (CPG) & AST Context Window Slicer.

Extracts minimal backward and forward dependency slices for massive (1,000+ line)
monolithic files to keep prompt sizes within the strict 2,000-token attention sweet spot
of local 3B and 8B models (qwen2.5-coder:3b).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class SlicedContextResult:
    """Outcome of an AST dependency slicing operation."""
    target_symbol_or_line: str
    original_line_count: int
    sliced_line_count: int
    compression_ratio: float
    referenced_symbols: Set[str] = field(default_factory=set)
    sliced_code: str = ""
    retained_functions: List[str] = field(default_factory=list)


class SymbolReferenceCollector(ast.NodeVisitor):
    """Collects variable names, function calls, and attribute references inside an AST subtree."""

    def __init__(self) -> None:
        self.references: Set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        self.references.add(node.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.references.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.references.add(node.func.attr)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.references.add(node.attr)
        self.generic_visit(node)


class CPGContextSlicer:
    """Extracts compact, functionally complete AST slices for local SLMs."""

    def __init__(self) -> None:
        pass

    def slice_file(
        self,
        source_code: str,
        target_line: Optional[int] = None,
        target_symbol: Optional[str] = None,
    ) -> SlicedContextResult:
        """Slices source code down to only the imports, helpers, and target scope."""
        lines = source_code.splitlines()
        orig_count = len(lines)

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # Fallback for unparseable syntax: sliding window around target line
            return self._sliding_window_fallback(lines, target_line, target_symbol)

        # 1. Collect top-level imports and global assignments
        imports: List[ast.stmt] = []
        global_defs: Dict[str, ast.stmt] = {}
        functions_and_classes: Dict[str, ast.stmt] = {}

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                functions_and_classes[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                # Record global variable assignments
                for target in getattr(node, "targets", [getattr(node, "target", None)]):
                    if isinstance(target, ast.Name):
                        global_defs[target.id] = node

        # 2. Identify target AST node
        target_node: Optional[ast.stmt] = None
        target_name = target_symbol or ""

        if target_symbol and target_symbol in functions_and_classes:
            target_node = functions_and_classes[target_symbol]
        elif target_line is not None:
            for name, node in functions_and_classes.items():
                start = getattr(node, "lineno", 0)
                end = getattr(node, "end_lineno", start)
                if start <= target_line <= end:
                    target_node = node
                    target_name = name
                    break

        if not target_node:
            # If no specific function matched, return sliding window fallback
            return self._sliding_window_fallback(lines, target_line, target_symbol)

        assert target_node is not None

        # 3. Backward dependency trace: find symbols used by the target node
        collector = SymbolReferenceCollector()
        collector.visit(target_node)
        needed_symbols: Set[str] = set(collector.references)

        # Transitive closure: iteratively collect symbols referenced by dependent functions
        visited_functions: Set[str] = set()
        changed = True
        while changed:
            changed = False
            for name, fn_node in functions_and_classes.items():
                if name in needed_symbols and name not in visited_functions:
                    visited_functions.add(name)
                    fn_collector = SymbolReferenceCollector()
                    fn_collector.visit(fn_node)
                    new_refs = fn_collector.references - needed_symbols
                    if new_refs:
                        needed_symbols.update(new_refs)
                        changed = True

        # 4. Resolve transitive dependencies across functions and global defs
        retained_nodes: List[ast.stmt] = list(imports)
        retained_fn_names: List[str] = []

        for name, g_node in global_defs.items():
            if name in needed_symbols:
                retained_nodes.append(g_node)

        for name, fn_node in functions_and_classes.items():
            if name == target_name:
                continue
            if name in needed_symbols:
                retained_nodes.append(fn_node)
                retained_fn_names.append(name)

        # Append target node at the end
        retained_nodes.append(target_node)
        retained_fn_names.append(target_name)

        # 5. Unparse the slice back to clean Python source code
        slice_module = ast.Module(body=retained_nodes, type_ignores=[])
        try:
            sliced_code = ast.unparse(slice_module)
        except Exception:
            sliced_code = "\n\n".join(
                "\n".join(lines[getattr(n, "lineno", 1) - 1 : getattr(n, "end_lineno", 1)])
                for n in retained_nodes
            )

        sliced_lines = len(sliced_code.splitlines())
        compression = round((1.0 - (sliced_lines / max(1, orig_count))) * 100, 1)

        return SlicedContextResult(
            target_symbol_or_line=target_name or str(target_line),
            original_line_count=orig_count,
            sliced_line_count=sliced_lines,
            compression_ratio=max(0.0, compression),
            referenced_symbols=needed_symbols,
            sliced_code=sliced_code,
            retained_functions=retained_fn_names,
        )

    def _sliding_window_fallback(
        self,
        lines: List[str],
        target_line: Optional[int],
        target_symbol: Optional[str],
    ) -> SlicedContextResult:
        """Sliding window fallback when AST parsing cannot isolate the scope."""
        center = target_line if target_line is not None else 1
        start = max(0, center - 25)
        end = min(len(lines), center + 25)
        sliced_lines = lines[start:end]
        code = "\n".join(sliced_lines)

        compression = round((1.0 - (len(sliced_lines) / max(1, len(lines)))) * 100, 1)
        return SlicedContextResult(
            target_symbol_or_line=target_symbol or str(target_line),
            original_line_count=len(lines),
            sliced_line_count=len(sliced_lines),
            compression_ratio=max(0.0, compression),
            referenced_symbols=set(),
            sliced_code=code,
            retained_functions=[],
        )
