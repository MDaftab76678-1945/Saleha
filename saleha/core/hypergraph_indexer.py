"""
Saleha Core: Multi-File AST Hypergraph Indexer & Symbol Dependency Engine

Indexes the entire codebase into an exact semantic Symbol Hypergraph:
1. Cross-File Symbol Declarations (Classes, Functions, Methods, Type Aliases).
2. Inter-Module Import Call Graphs & Inheritance Hierarchies.
3. Upstream & Downstream Impact Analysis for targeted multi-file context injection.
4. Sub-millisecond graph query resolution for large codebases.
"""

from __future__ import annotations

import ast
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple


@dataclass
class SymbolNode:
    symbol_name: str
    symbol_type: str  # 'class', 'function', 'method', 'variable', 'module'
    file_path: str
    line_number: int
    docstring: str = ""
    parameters: List[str] = field(default_factory=list)
    return_type: str = "Any"
    dependencies: Set[str] = field(default_factory=set)  # symbols/modules this node depends on
    callers: Set[str] = field(default_factory=set)       # symbols that call or reference this node
    outgoing_calls: Set[str] = field(default_factory=set) # symbol names invoked inside this node
    scope: str = ""                                      # enclosing scope (e.g. class name)


@dataclass
class HypergraphIndexStats:
    total_files_scanned: int
    total_symbols_indexed: int
    total_dependency_edges: int
    indexing_duration_ms: float
    modules_indexed: List[str]


class _HypergraphASTVisitor(ast.NodeVisitor):
    """Scoped AST visitor extracting declarations, base classes, imports, and calls."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path: str = rel_path
        self.nodes: List[SymbolNode] = []
        self.imports: Set[str] = set()
        self._scope_stack: List[str] = []
        self._current_node: Optional[SymbolNode] = None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            full_name = f"{mod}.{alias.name}" if mod else alias.name
            self.imports.add(full_name)
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        doc = ast.get_docstring(node) or ""
        bases: Set[str] = set()
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.add(b.id)
            elif isinstance(b, ast.Attribute):
                bases.add(ast.unparse(b))

        scope_prefix = ".".join(self._scope_stack)
        full_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name

        s_node = SymbolNode(
            symbol_name=full_name,
            symbol_type="class",
            file_path=self.rel_path,
            line_number=node.lineno,
            docstring=doc[:200],
            dependencies=bases,
            scope=scope_prefix,
        )
        self.nodes.append(s_node)

        # Enter class scope
        self._scope_stack.append(node.name)
        old_node = self._current_node
        self._current_node = s_node
        self.generic_visit(node)
        self._current_node = old_node
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_func(node)

    def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        doc = ast.get_docstring(node) or ""
        params: List[str] = []
        for a in getattr(node.args, "posonlyargs", []):
            params.append(a.arg)
        for a in node.args.args:
            params.append(a.arg)
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}")
        for a in getattr(node.args, "kwonlyargs", []):
            params.append(a.arg)
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}")

        ret = ast.unparse(node.returns) if node.returns else "Any"
        scope_prefix = ".".join(self._scope_stack)
        is_method = bool(self._scope_stack)
        sym_type = "method" if is_method else "function"
        full_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name

        s_node = SymbolNode(
            symbol_name=full_name,
            symbol_type=sym_type,
            file_path=self.rel_path,
            line_number=node.lineno,
            docstring=doc[:200],
            parameters=params,
            return_type=ret,
            scope=scope_prefix,
        )
        self.nodes.append(s_node)

        # Enter function scope
        self._scope_stack.append(node.name)
        old_node = self._current_node
        self._current_node = s_node
        self.generic_visit(node)
        self._current_node = old_node
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        callee = ""
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = node.func.attr
        if callee and self._current_node is not None:
            self._current_node.outgoing_calls.add(callee)
        self.generic_visit(node)


class HypergraphIndexer:
    """High-speed AST-based semantic hypergraph indexer."""

    def __init__(self, root_dir: Optional[str] = None) -> None:
        self.root_dir: str = root_dir or os.getcwd()
        self.symbols: Dict[str, SymbolNode] = {}
        self.file_to_symbols: Dict[str, List[str]] = {}
        self.file_imports: Dict[str, Set[str]] = {}

    def scan_directory(self, target_dir: Optional[str] = None) -> HypergraphIndexStats:
        """Scans Python files and builds the bidirectional symbol hypergraph."""
        start_t = time.perf_counter()
        scan_root = target_dir or os.path.join(self.root_dir, "saleha")
        self.symbols.clear()
        self.file_to_symbols.clear()
        self.file_imports.clear()

        files_scanned = 0
        edges_count = 0

        if not os.path.exists(scan_root):
            scan_root = self.root_dir

        for root, dirs, files in os.walk(scan_root):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".venv", "node_modules")]
            for file in sorted(files):
                if file.endswith(".py"):
                    full_p = os.path.join(root, file)
                    rel_path = os.path.relpath(full_p, self.root_dir).replace("\\", "/")
                    files_scanned += 1
                    file_symbols = self._index_file(full_p, rel_path)
                    self.file_to_symbols[rel_path] = file_symbols

        # Build reverse short-name lookup for resolving unadorned function/class calls
        name_to_nodes: Dict[str, List[SymbolNode]] = {}
        for node in self.symbols.values():
            short = node.symbol_name.split(".")[-1]
            name_to_nodes.setdefault(short, []).append(node)

        # Second Pass: Link cross-symbol dependencies and callers
        for sym_name, node in self.symbols.items():
            # 1. Base class inheritance edges
            for base in list(node.dependencies):
                if base in self.symbols:
                    self.symbols[base].callers.add(sym_name)
                elif base in name_to_nodes:
                    for target in name_to_nodes[base]:
                        target.callers.add(sym_name)

            # 2. Outgoing function/method call edges
            for callee in node.outgoing_calls:
                if callee in self.symbols:
                    node.dependencies.add(callee)
                    self.symbols[callee].callers.add(sym_name)
                elif callee in name_to_nodes:
                    for target in name_to_nodes[callee]:
                        node.dependencies.add(target.symbol_name)
                        target.callers.add(sym_name)

            edges_count += len(node.dependencies)

        duration = (time.perf_counter() - start_t) * 1000

        return HypergraphIndexStats(
            total_files_scanned=files_scanned,
            total_symbols_indexed=len(self.symbols),
            total_dependency_edges=edges_count,
            indexing_duration_ms=round(duration, 2),
            modules_indexed=list(self.file_to_symbols.keys())[:15],
        )

    def _index_file(self, full_path: str, rel_path: str) -> List[str]:
        """Parses a single file with AST and extracts scoped symbols."""
        extracted: List[str] = []
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content)
        except Exception:
            return extracted

        visitor = _HypergraphASTVisitor(rel_path)
        visitor.visit(tree)

        self.file_imports[rel_path] = visitor.imports

        for node in visitor.nodes:
            self.symbols[node.symbol_name] = node
            extracted.append(node.symbol_name)

            # If symbol is a method or scoped function, also map short name if not occupied
            short_name = node.symbol_name.split(".")[-1]
            if short_name not in self.symbols:
                self.symbols[short_name] = node

        return extracted

    def get_symbol_context(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Returns full dependency graph and code context for a given symbol."""
        node = self.symbols.get(symbol_name)
        if not node:
            # Suffix search: e.g. "route" matches "SmartRouter.route"
            for name, candidate in self.symbols.items():
                if name.endswith(f".{symbol_name}"):
                    node = candidate
                    break
        if not node:
            return None

        return {
            "symbol": node.symbol_name,
            "type": node.symbol_type,
            "file": node.file_path,
            "line": node.line_number,
            "parameters": node.parameters,
            "return_type": node.return_type,
            "dependencies": sorted(list(node.dependencies)),
            "callers": sorted(list(node.callers)),
            "outgoing_calls": sorted(list(node.outgoing_calls)),
            "docstring": node.docstring,
        }

    def find_impacted_files(self, symbol_name: str) -> List[str]:
        """Finds all files that depend on, inherit from, or call this symbol."""
        impacted: Set[str] = set()
        node = self.symbols.get(symbol_name)

        # 1. Any symbol with symbol_name in dependencies or outgoing calls
        for s_node in self.symbols.values():
            if symbol_name in s_node.dependencies or symbol_name in s_node.outgoing_calls:
                impacted.add(s_node.file_path)

        # 2. Registered callers of this node
        if node:
            for caller in node.callers:
                if caller in self.symbols:
                    impacted.add(self.symbols[caller].file_path)

            # If class, check callers of all its scoped methods
            if node.symbol_type == "class":
                prefix = f"{symbol_name}."
                for m_name, m_node in self.symbols.items():
                    if m_name.startswith(prefix):
                        for c in m_node.callers:
                            if c in self.symbols:
                                impacted.add(self.symbols[c].file_path)

        # 3. Check import references across files
        short_name = symbol_name.split(".")[-1]
        for fpath, imps in self.file_imports.items():
            if symbol_name in imps or short_name in imps:
                impacted.add(fpath)

        return sorted(list(impacted))


hypergraph_indexer = HypergraphIndexer()
