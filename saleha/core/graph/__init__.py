"""
Saleha Core: Graph Engineering Subsystem (2026 Frontier Standard)

Provides AST symbol extraction, multi-hop call graphs, dependency topologies,
and cross-file impact analysis:
- CodebaseIndexer / codebase_indexer & SmartPatcher / smart_patcher
- CodebaseDependencyGraph / dependency_graph (Module import & callgraph topology)
- MultiRepoDependencyGraph / multi_repo_graph (Cross-repo architectural dependencies)
- HierarchicalGraphMemory / graph_memory (Entity-relation knowledge graph)
- HypergraphIndexer / hypergraph_indexer (Multi-hop hyperedge code relationship graph)
- CallGraphNavigator (Multi-hop topological path search connecting callers to callees)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Set, Tuple

from saleha.core.graph.codebase_indexer import (
    ClassSymbol,
    CodebaseIndexer,
    FunctionSymbol,
    SmartPatcher,
    codebase_indexer,
    smart_patcher,
)
from saleha.core.graph.dependency_graph import (
    CodebaseDependencyGraph,
    SymbolLocation,
    SymbolReference,
    dependency_graph,
)
from saleha.core.graph.graph_memory import (
    GraphEdge,
    GraphNode,
    HierarchicalGraphMemory,
    graph_memory,
)
from saleha.core.graph.hypergraph_indexer import (
    HypergraphIndexer,
    HypergraphIndexStats,
    SymbolNode,
    hypergraph_indexer,
)
from saleha.core.graph.multi_repo_graph import (
    CrossRepoImpact,
    MultiRepoDependencyGraph,
    RepoMetadata,
    multi_repo_graph,
)
from saleha.core.graph.system1_scout import (
    ScoutDossier,
    SymbolDossier,
    System1Scout,
    system1_scout,
)



class CallGraphNavigator:
    """
    2026 Graph Engineering Navigator:
    Performs multi-hop graph queries across symbol callgraphs and dependency topologies.
    Enables questions like: 'Find all endpoints affected if UserRepository.save is modified.'
    """

    def __init__(self):
        self.dep_graph = dependency_graph
        self.hypergraph = hypergraph_indexer

    def find_multi_hop_callers(self, target_symbol: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Walks upstream callers across multiple hops to identify blast radius."""
        visited: Set[str] = set()
        queue: List[Tuple[str, int, List[str]]] = [(target_symbol, 0, [target_symbol])]
        results = []

        while queue:
            current, depth, path = queue.pop(0)
            if depth >= max_depth:
                continue

            callers = self.dep_graph.find_callers(current)
            for c in callers:
                caller_sym = os.path.basename(c.caller_file)
                if caller_sym not in visited:
                    visited.add(caller_sym)
                    new_path = path + [f"{c.caller_file}:{c.caller_line}"]
                    results.append({
                        "symbol": current,
                        "caller_file": c.caller_file,
                        "caller_line": c.caller_line,
                        "depth": depth + 1,
                        "path": new_path,
                    })
                    queue.append((caller_sym, depth + 1, new_path))

        return results

    def trace_impact_radius(self, symbol_name: str) -> Dict[str, Any]:
        """Calculates total downstream and upstream blast radius for a symbol."""
        impacted_files = self.hypergraph.find_impacted_files(symbol_name)
        callers = self.dep_graph.find_callers(symbol_name)
        return {
            "symbol": symbol_name,
            "direct_caller_count": len(callers),
            "impacted_files_count": len(impacted_files),
            "impacted_files": impacted_files,
            "callers": [
                {"file": c.caller_file, "line": c.caller_line, "context": c.caller_context}
                for c in callers
            ],
        }


call_graph_navigator = CallGraphNavigator()


__all__ = [
    "CodebaseIndexer",
    "codebase_indexer",
    "SmartPatcher",
    "smart_patcher",
    "FunctionSymbol",
    "ClassSymbol",
    "CodebaseDependencyGraph",
    "dependency_graph",
    "SymbolLocation",
    "SymbolReference",
    "MultiRepoDependencyGraph",
    "multi_repo_graph",
    "RepoMetadata",
    "CrossRepoImpact",
    "HierarchicalGraphMemory",
    "graph_memory",
    "GraphNode",
    "GraphEdge",
    "HypergraphIndexer",
    "hypergraph_indexer",
    "SymbolNode",
    "HypergraphIndexStats",
    "CallGraphNavigator",
    "call_graph_navigator",
    "System1Scout",
    "system1_scout",
    "ScoutDossier",
    "SymbolDossier",
]
