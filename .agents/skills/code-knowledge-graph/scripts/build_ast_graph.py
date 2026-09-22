#!/usr/bin/env python3
"""AST Call-Graph and Topological Dependency DAG Builder.

Parses Python source files into an interconnected knowledge graph representing
classes, functions, inheritance chains, and call-site edges.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Any

REPO_ROOT = Path(__file__).resolve().parents[4]


class ASTGraphExtractor(ast.NodeVisitor):
    """Visits AST nodes to extract symbols and relationship edges."""

    def __init__(self, file_rel_path: str) -> None:
        self.file_rel_path = file_rel_path.replace("\\", "/")
        self.symbols: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, str]] = []
        self._current_scope: List[str] = [self.file_rel_path]

    def _qual_name(self, name: str) -> str:
        return "::".join(self._current_scope + [name])

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qname = self._qual_name(node.name)
        base_names = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                base_names.append(b.id)
            elif isinstance(b, ast.Attribute):
                base_names.append(b.attr)

        self.symbols[qname] = {
            "type": "class",
            "name": node.name,
            "line": node.lineno,
            "bases": base_names,
            "file": self.file_rel_path,
        }

        for base in base_names:
            self.edges.append({"source": qname, "target": base, "type": "inherits"})

        self._current_scope.append(node.name)
        self.generic_visit(node)
        self._current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qname = self._qual_name(node.name)
        self.symbols[qname] = {
            "type": "function",
            "name": node.name,
            "line": node.lineno,
            "args": [a.arg for a in node.args.args],
            "file": self.file_rel_path,
        }
        self._current_scope.append(node.name)
        self.generic_visit(node)
        self._current_scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_Call(self, node: ast.Call) -> None:
        caller = "::".join(self._current_scope)
        called = None
        if isinstance(node.func, ast.Name):
            called = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called = node.func.attr

        if called and caller != self.file_rel_path:
            self.edges.append({"source": caller, "target": called, "type": "calls"})

        self.generic_visit(node)


def build_knowledge_graph(target_dir: Path) -> Dict[str, Any]:
    """Scans all Python files under target_dir and creates graph representation."""
    all_symbols: Dict[str, Dict[str, Any]] = {}
    all_edges: List[Dict[str, str]] = []

    for path in sorted(target_dir.rglob("*.py")):
        rel_parts = path.parts
        if any(p.startswith(".") or p == "__pycache__" for p in rel_parts):
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue

        rel_path = str(path.relative_to(REPO_ROOT if REPO_ROOT in path.parents else target_dir))
        extractor = ASTGraphExtractor(rel_path)
        extractor.visit(tree)

        all_symbols.update(extractor.symbols)
        all_edges.extend(extractor.edges)

    # Calculate metrics
    in_degrees: Dict[str, int] = {}
    out_degrees: Dict[str, int] = {}
    for edge in all_edges:
        src = edge["source"]
        tgt = edge["target"]
        out_degrees[src] = out_degrees.get(src, 0) + 1
        in_degrees[tgt] = in_degrees.get(tgt, 0) + 1

    top_called = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "status": "success",
        "total_symbols": len(all_symbols),
        "total_edges": len(all_edges),
        "top_referenced_symbols": top_called,
        "symbols": all_symbols,
        "edges": all_edges,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and query repository AST Knowledge Graph."
    )
    parser.add_argument("--target", "-t", default="saleha/core", help="Target directory to scan.")
    parser.add_argument("--output", "-o", default=None, help="Output destination JSON path.")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()
    if not target_path.exists():
        sys.stderr.write(f"Target directory not found: {target_path}\n")
        return 1

    graph = build_knowledge_graph(target_path)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        print(f"Knowledge graph ({graph['total_symbols']} symbols, {graph['total_edges']} edges) written to: {out_path}")
    else:
        print(f"Total Symbols: {graph['total_symbols']}")
        print(f"Total Edges: {graph['total_edges']}")
        print("Top Referenced Symbols:")
        for sym, count in graph["top_referenced_symbols"]:
            print(f"  {sym:30s} -> {count} calls")

    return 0


if __name__ == "__main__":
    sys.exit(main())
