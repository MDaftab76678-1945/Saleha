"""
Saleha Core: Hierarchical Semantic Graph Memory (GraphMemory)

Implements a non-Euclidean directed knowledge graph for multi-agent memory:
1. Directed graph of TaskNode -> ModuleNode -> FunctionNode -> TestNode.
2. Semantic relationship edges (CONTAINS, IMPLEMENTS, VERIFIES, DEPENDS_ON).
3. Hierarchical subgraph traversal and Mermaid diagram visualization.
4. Persistent storage in ~/.saleha/graph_memory.json.
"""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


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
        # Why the stored memory could not be read ("" if it could, or if there
        # was none), and where an unreadable file was moved to.
        self.load_error = ""
        self.quarantined_to = ""
        self._load()

    @staticmethod
    def stable_id(prefix: str, text: str) -> str:
        """Same text -> same id in every process.

        The ids used to come from the builtin hash(), which is salted per
        process: the same goal got a different id on every run, so a stored
        memory was never found again and every re-record added a duplicate.
        """
        return f"{prefix}_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"

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
        """Adds a directional relation between two nodes (once: a repeat updates the weight)."""
        for existing in self.edges:
            if (existing.source_id, existing.target_id, existing.relation) == (source_id, target_id, relation):
                existing.weight = weight
                return existing
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
        goal_id = self.stable_id("task", goal)
        self.add_node(goal_id, goal, "task", {"goal": goal})

        mod_id = self.stable_id("mod", module_name)
        self.add_node(mod_id, module_name, "module", {"module_name": module_name})
        self.add_edge(goal_id, mod_id, "CONTAINS")

        for fn in functions:
            # Keyed by module and name: two modules may both define `run`.
            fn_id = self.stable_id("fn", f"{module_name}::{fn.get('name', '')}")
            self.add_node(fn_id, fn.get("name", "function"), "function", fn)
            self.add_edge(mod_id, fn_id, "IMPLEMENTS")

        for test in tests:
            test_id = self.stable_id("test", f"{module_name}::{test}")
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

    def save(self) -> None:
        """Persists graph memory to disk atomically.

        Raises OSError when it cannot write. It used to swallow that, so a
        memory that never reached disk was reported as recorded.
        """
        directory = os.path.dirname(self.store_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        data = {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "edges": [asdict(e) for e in self.edges],
        }
        tmp = self.store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.store_path)

    def _load(self) -> None:
        """Loads graph memory from disk if available.

        A file that cannot be read is moved aside, never left in place: the
        next save() would otherwise overwrite it with an empty graph and the
        stored memory would be gone for good. `load_error` says what happened.
        """
        if not os.path.exists(self.store_path) or os.path.getsize(self.store_path) == 0:
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = {k: GraphNode(**v) for k, v in data.get("nodes", {}).items()}
            edges = [GraphEdge(**e) for e in data.get("edges", [])]
        except (OSError, ValueError, TypeError, AttributeError) as err:
            self.load_error = f"{type(err).__name__}: {err}"
            aside = f"{self.store_path}.corrupt-{int(time.time())}"
            try:
                os.replace(self.store_path, aside)
                self.quarantined_to = aside
            except OSError as move_err:
                self.load_error += f" (and it could not be moved aside: {move_err})"
            return
        self.nodes, self.edges = nodes, edges


_graph_memory_singleton: Optional[HierarchicalGraphMemory] = None


def __getattr__(name: str) -> Any:
    """Lazy `graph_memory` singleton: constructing it reads (and may move
    aside) the user's store, which must not happen as an import side effect."""
    global _graph_memory_singleton
    if name == "graph_memory":
        if _graph_memory_singleton is None:
            _graph_memory_singleton = HierarchicalGraphMemory()
        return _graph_memory_singleton
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    _gm = HierarchicalGraphMemory()
    _gm.record_solution_hierarchy(
        goal="Calculator API",
        module_name="calculator.py",
        functions=[{"name": "add", "signature": "def add(a, b)"}],
        tests=["test_add"],
    )
