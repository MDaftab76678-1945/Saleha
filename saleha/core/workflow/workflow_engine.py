"""
Saleha Workflow Engine: Topological DAG Graph & Autonomous Parallel Execution Kernel.

Coordinates multi-branch DAG execution, topological batching, parallel threading,
cascading failure containment, and real-time event telemetry for SalehaFlow.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from saleha.core.workflow.nodes import (
    NodeStatus,
    WorkflowExecutionContext,
    WorkflowNode,
    ActionNode,
    CodeNode,
    HTTPNode,
    ConditionNode,
    AgentNode,
)
from saleha.core.workflow.self_healing_node import SelfHealingNode
from saleha.core.workflow.verified_sandbox_node import VerifiedSandboxNode
from saleha.core.workflow.bft_consensus_node import BFTConsensusNode
from saleha.core.workflow.triggers import TriggerNode, CronTrigger, WebhookTrigger


@dataclass
class WorkflowExecutionResult:
    """Complete summary of an executed workflow DAG."""
    workflow_id: str
    execution_id: str
    success: bool
    total_nodes: int
    completed_nodes: List[str] = field(default_factory=list)
    healed_nodes: List[str] = field(default_factory=list)
    failed_nodes: List[str] = field(default_factory=list)
    skipped_nodes: List[str] = field(default_factory=list)
    total_duration_ms: float = 0.0
    node_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blackboard_snapshot: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


class WorkflowDAG:
    """
    Topological DAG execution engine with parallel dispatch,
    cycle validation, and visual graph interchange.
    """

    def __init__(
        self,
        workflow_id: Optional[str] = None,
        name: str = "Untitled Workflow",
        description: str = "",
    ) -> None:
        self.workflow_id = workflow_id or f"wf_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}

    def add_node(self, node: WorkflowNode) -> "WorkflowDAG":
        self.nodes[node.id] = node
        return self

    def connect(self, source_id: str, target_id: str) -> "WorkflowDAG":
        """Adds a directed dependency edge from source_id to target_id."""
        if source_id not in self.nodes:
            raise KeyError(f"Source node '{source_id}' does not exist in workflow.")
        if target_id not in self.nodes:
            raise KeyError(f"Target node '{target_id}' does not exist in workflow.")
        target = self.nodes[target_id]
        if source_id not in target.depends_on:
            target.depends_on.append(source_id)
        return self

    def get_topological_batches(self) -> List[List[WorkflowNode]]:
        """
        Calculates execution order in parallel stages using dependency resolution.
        Raises ValueError if a circular dependency is detected.
        """
        # Validate that all dependencies exist
        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    raise KeyError(
                        f"Node '{nid}' depends on unknown node '{dep}'."
                    )

        completed: Set[str] = set()
        batches: List[List[WorkflowNode]] = []

        while len(completed) < len(self.nodes):
            current_batch = [
                node for nid, node in self.nodes.items()
                if nid not in completed and all(dep in completed for dep in node.depends_on)
            ]
            if not current_batch:
                remaining_ids = [nid for nid in self.nodes if nid not in completed]
                raise ValueError(
                    f"Circular dependency detected among workflow nodes: {remaining_ids}"
                )

            batches.append(current_batch)
            for node in current_batch:
                completed.add(node.id)

        return batches

    def execute(
        self,
        context: Optional[WorkflowExecutionContext] = None,
        max_workers: int = 4,
    ) -> WorkflowExecutionResult:
        """
        Executes the workflow graph topologically with concurrent stage dispatching.
        """
        start_time = time.time()
        ctx = context or WorkflowExecutionContext(
            workflow_id=self.workflow_id,
            execution_id=f"exec_{uuid.uuid4().hex[:8]}",
        )
        ctx.log(f"Starting workflow '{self.name}' ({self.workflow_id})")

        batches = self.get_topological_batches()
        completed_nodes: List[str] = []
        healed_nodes: List[str] = []
        failed_nodes: List[str] = []
        skipped_nodes: List[str] = []
        node_results: Dict[str, Dict[str, Any]] = {}

        for batch in batches:
            runnable_nodes: List[WorkflowNode] = []
            for node in batch:
                # Check upstream failures
                broken_deps = [
                    dep for dep in node.depends_on
                    if self.nodes[dep].status in (NodeStatus.FAILED, NodeStatus.SKIPPED)
                ]
                if broken_deps:
                    node.status = NodeStatus.SKIPPED
                    node.error = f"Skipped due to upstream failed dependencies: {broken_deps}"
                    skipped_nodes.append(node.id)
                    node_results[node.id] = {
                        "status": node.status.value,
                        "duration_ms": 0.0,
                        "outputs": {},
                        "error": node.error,
                        "metadata": node.metadata,
                    }
                    ctx.log(f"Node '{node.id}' SKIPPED due to {broken_deps}")
                else:
                    runnable_nodes.append(node)

            if not runnable_nodes:
                continue

            # Execute batch
            def _run_single_node(n: WorkflowNode) -> WorkflowNode:
                n.status = NodeStatus.RUNNING
                n_start = time.time()
                ctx.emit_event("node_start", {"node_id": n.id, "title": n.title})
                try:
                    out = n.execute(ctx)
                    n.duration_ms = round((time.time() - n_start) * 1000, 2)
                    ctx.set_output(n.id, out)
                    if n.status == NodeStatus.HEALED:
                        ctx.emit_event("node_healed", {"node_id": n.id, "duration_ms": n.duration_ms})
                    else:
                        n.status = NodeStatus.COMPLETED
                        ctx.emit_event("node_complete", {"node_id": n.id, "duration_ms": n.duration_ms})
                except Exception as e:
                    n.duration_ms = round((time.time() - n_start) * 1000, 2)
                    n.status = NodeStatus.FAILED
                    n.error = str(e)
                    ctx.emit_event("node_failed", {"node_id": n.id, "error": str(e)})
                return n

            with ThreadPoolExecutor(max_workers=min(max_workers, len(runnable_nodes) or 1)) as pool:
                futures = [pool.submit(_run_single_node, n) for n in runnable_nodes]
                for f in as_completed(futures):
                    res_node = f.result()
                    node_results[res_node.id] = {
                        "status": res_node.status.value,
                        "duration_ms": res_node.duration_ms,
                        "outputs": ctx.get_output(res_node.id),
                        "error": res_node.error,
                        "metadata": res_node.metadata,
                    }
                    if res_node.status == NodeStatus.COMPLETED:
                        completed_nodes.append(res_node.id)
                    elif res_node.status == NodeStatus.HEALED:
                        healed_nodes.append(res_node.id)
                    elif res_node.status == NodeStatus.FAILED:
                        failed_nodes.append(res_node.id)

        total_duration = round((time.time() - start_time) * 1000, 2)
        overall_success = len(failed_nodes) == 0 and len(skipped_nodes) == 0

        ctx.log(
            f"Workflow finished: success={overall_success} in {total_duration}ms "
            f"(Completed: {len(completed_nodes)}, Healed: {len(healed_nodes)}, Failed: {len(failed_nodes)})"
        )

        return WorkflowExecutionResult(
            workflow_id=self.workflow_id,
            execution_id=ctx.execution_id,
            success=overall_success,
            total_nodes=len(self.nodes),
            completed_nodes=completed_nodes,
            healed_nodes=healed_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            total_duration_ms=total_duration,
            node_results=node_results,
            blackboard_snapshot=dict(ctx.blackboard),
            logs=list(ctx.logs),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes workflow into visual JSON DAG for Web Studio / REST API."""
        nodes_list = []
        connections = []

        for nid, node in self.nodes.items():
            nodes_list.append(node.to_dict())
            for dep in node.depends_on:
                connections.append({
                    "from": dep,
                    "to": nid,
                })

        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "nodes": nodes_list,
            "connections": connections,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDAG":
        """Deserializes a visual JSON DAG into an executable WorkflowDAG."""
        dag = cls(
            workflow_id=data.get("workflow_id"),
            name=data.get("name", "Imported Workflow"),
            description=data.get("description", ""),
        )
        for n_data in data.get("nodes", []):
            nid = n_data["id"]
            title = n_data.get("title", nid)
            ntype = n_data.get("type", "generic")
            deps = n_data.get("depends_on", [])
            cfg = n_data.get("config", {})

            if ntype == "code":
                node = CodeNode(nid, title, code_str=cfg.get("code", "outputs = {}"), depends_on=deps, config=cfg)
            elif ntype == "http":
                node = HTTPNode(nid, title, url=cfg.get("url", ""), method=cfg.get("method", "GET"), depends_on=deps, config=cfg)
            elif ntype == "condition":
                node = ConditionNode(nid, title, expression=cfg.get("expression"), depends_on=deps, config=cfg)
            elif ntype == "agent":
                node = AgentNode(nid, title, prompt_template=cfg.get("prompt", ""), depends_on=deps, config=cfg)
            elif ntype == "verified_sandbox":
                node = VerifiedSandboxNode(nid, title, code_str=cfg.get("code", ""), depends_on=deps, config=cfg)
            else:
                node = ActionNode(nid, title, action_fn=lambda inp, ctx: inp, depends_on=deps, config=cfg)

            dag.add_node(node)

        # Wire connections
        for conn in data.get("connections", []):
            dag.connect(conn["from"], conn["to"])

        return dag

    def to_mermaid(self) -> str:
        """Generates safe ASCII Mermaid flowchart diagram."""
        lines = ["flowchart TD"]
        for nid, node in self.nodes.items():
            badge = f"[{node.status.value}] " if node.status != NodeStatus.PENDING else ""
            lines.append(f'    {nid}["{badge}{node.title} ({node.node_type})"]')
            for dep in node.depends_on:
                lines.append(f"    {dep} --> {nid}")
        return "\n".join(lines)
