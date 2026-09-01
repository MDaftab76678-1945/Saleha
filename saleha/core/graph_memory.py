"""
Saleha Core: Hierarchical Semantic Graph Memory (GraphMemory)

Implements a non-Euclidean directed knowledge graph for multi-agent memory:
1. Directed graph of TaskNode -> ModuleNode -> FunctionNode -> TestNode.
2. Semantic relationship edges (CONTAINS, IMPLEMENTS, VERIFIES, DEPENDS_ON).
3. Hierarchical subgraph traversal and Mermaid diagram visualization.
4. Persistent storage in ~/.saleha/graph_memory.json.
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Set


@dataclass
class GraphNode:
    """Represents an entity node in the semantic graph."""
    node_id: str
    label: str
    node_type: str  # "task", "module", "function", "test", "concept"
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class GraphEdge:
    """Represents a directional relationship between two graph nodes."""
    source_id: str
    target_id: str
    relation: str  # "CONTAINS", "IMPLEMENTS", "VERIFIES", "DEPENDS_ON"
    weight: float = 1.0


class HierarchicalGraphMemory:
    """Hierarchical graph memory store for structured semantic recall."""

    DEFAULT_STORE_PATH = os.path.expanduser("~/.saleha/graph_memory.json")

    def __init__(self, store_path: Optional[str] = None):
        """Initializes the hierarchical graph memory."""
        self.store_path = store_path or self.DEFAULT_STORE_PATH
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._load()

    def add_node(self, node_id: str, label: str, node_type: str, properties: Optional[Dict[str, Any]] = None) -> GraphNode:
        """Adds or updates a node in the graph."""
        node = GraphNode(
            node_id=node_id,
            label=label,
            node_type=node_type,
            properties=properties or {},
        )
        self.nodes[node_id] = node
        return node

    def add_edge(self, source_id: str, target_id: str, relation: str, weight: float = 1.0) -> GraphEdge:
        """Adds a directional relation between two nodes."""
        edge = GraphEdge(source_id=source_id, target_id=target_id, relation=relation, weight=weight)
        self.edges.append(edge)
        return edge

    def record_solution_hierarchy(
        self,
        goal: str,
        module_name: str,
        functions: List[Dict[str, str]],
        tests: List[str],
    ):
        """Helper to index a complete hierarchical solution into the graph."""
        goal_id = f"task_{abs(hash(goal)) % 100000}"
        self.add_node(goal_id, goal, "task", {"goal": goal})

        mod_id = f"mod_{abs(hash(module_name)) % 100000}"
        self.add_node(mod_id, module_name, "module", {"module_name": module_name})
        self.add_edge(goal_id, mod_id, "CONTAINS")

        for fn in functions:
            fn_id = f"fn_{abs(hash(fn.get('name', ''))) % 100000}"
            self.add_node(fn_id, fn.get("name", "function"), "function", fn)
            self.add_edge(mod_id, fn_id, "IMPLEMENTS")

        for test in tests:
            test_id = f"test_{abs(hash(test)) % 100000}"
            self.add_node(test_id, test, "test", {"test_name": test})
            self.add_edge(mod_id, test_id, "VERIFIES")

        self.save()

    def query_subgraph(self, root_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Traverses the graph starting from root_id up to max_depth."""
        visited_nodes: Set[str] = set()
        collected_nodes: List[Dict[str, Any]] = []
        collected_edges: List[Dict[str, Any]] = []

        def _dfs(current_id: str, depth: int):
            if depth > max_depth or current_id in visited_nodes:
                return
            visited_nodes.add(current_id)
            if current_id in self.nodes:
                collected_nodes.append(asdict(self.nodes[current_id]))

            for edge in self.edges:
                if edge.source_id == current_id:
                    collected_edges.append(asdict(edge))
                    _dfs(edge.target_id, depth + 1)

        _dfs(root_id, 0)
        return {"nodes": collected_nodes, "edges": collected_edges}

    def export_mermaid(self) -> str:
        """Generates a Mermaid diagram representing the graph structure."""
        lines = ["graph TD"]
        for node_id, node in self.nodes.items():
            clean_label = node.label.replace('"', "'")[:30]
            lines.append(f'    {node_id}["{node.node_type}: {clean_label}"]')

        for edge in self.edges:
            lines.append(f'    {edge.source_id} -->|{edge.relation}| {edge.target_id}')

        return "\n".join(lines)

    def save(self):
        """Persists graph memory to disk."""
        try:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            data = {
                "nodes": {k: asdict(v) for k, v in self.nodes.items()},
                "edges": [asdict(e) for e in self.edges],
            }
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except (OSError, IOError):
            pass  # noqa

    def _load(self):
        """Loads graph memory from disk if available."""
        if not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.nodes = {k: GraphNode(**v) for k, v in data.get("nodes", {}).items()}
            self.edges = [GraphEdge(**e) for e in data.get("edges", [])]
        except (OSError, IOError, json.JSONDecodeError):
            pass  # noqa


graph_memory = HierarchicalGraphMemory()


if __name__ == "__main__":
    _gm = HierarchicalGraphMemory()
    _gm.record_solution_hierarchy(
        goal="Calculator API",
        module_name="calculator.py",
        functions=[{"name": "add", "signature": "def add(a, b)"}],
        tests=["test_add"],
    )
