"""
Saleha Core: Parallel DAG Task Graph Engine

Constructs Directed Acyclic Graphs (DAGs) for complex software development tasks,
resolves dependencies via topological sorting, and executes independent tasks in
parallel using ThreadPoolExecutor while coordinating multi-agent swarms.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.core.agent_profile_loader import profile_registry, ProfileAgent


@dataclass
class TaskNode:
    id: str
    title: str
    role_profile: str  # Profile ID (e.g. 'agent_software_designer', 'agent_sde')
    prompt: str
    depends_on: List[str] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    result: str = ""
    error: str = ""
    duration: float = 0.0


@dataclass
class DAGResult:
    success: bool
    goal: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_time: float
    nodes: Dict[str, TaskNode] = field(default_factory=dict)
    mermaid_graph: str = ""


class TaskDAG:
    def __init__(self, goal: str = "", model: str = "auto"):
        self.goal = goal
        self.model = model
        self.nodes: Dict[str, TaskNode] = {}

    def add_task(self, node: TaskNode):
        self.nodes[node.id] = node

    def get_topological_batches(self) -> List[List[TaskNode]]:
        """Groups tasks into parallel execution stages (batches) based on dependencies."""
        in_degree = {task_id: len(node.depends_on) for task_id, node in self.nodes.items()}
        completed: Set[str] = set()
        batches: List[List[TaskNode]] = []

        while len(completed) < len(self.nodes):
            current_batch = [
                node for task_id, node in self.nodes.items()
                if task_id not in completed and all(dep in completed for dep in node.depends_on)
            ]
            if not current_batch:
                remaining_ids = [tid for tid in self.nodes if tid not in completed]
                raise ValueError(
                    f"Circular dependency detected among tasks: {remaining_ids}. "
                    f"Cannot resolve execution order."
                )

            batches.append(current_batch)
            for node in current_batch:
                completed.add(node.id)

        return batches

    def to_mermaid(self) -> str:
        """Exports DAG structure in Mermaid syntax."""
        lines = ["flowchart TD", f'    Goal["🎯 {self.goal or "Software Delivery"}"]']
        for node in self.nodes.values():
            status_emoji = "✅" if node.status == "COMPLETED" else ("❌" if node.status == "FAILED" else "⏳")
            lines.append(f'    {node.id}["{status_emoji} {node.title} ({node.role_profile})"]')
            if not node.depends_on:
                lines.append(f"    Goal --> {node.id}")
            for dep in node.depends_on:
                if dep in self.nodes:
                    lines.append(f"    {dep} --> {node.id}")
        return "\n".join(lines)

    def _get_agent_for_node(self, profile_id: str) -> BaseAgent:
        profile = profile_registry.get(profile_id)
        if profile:
            return ProfileAgent(profile=profile, model=self.model)
        return BaseAgent(role=profile_id, model=self.model)

    def _execute_node(self, node: TaskNode, context: Dict[str, str]) -> TaskNode:
        node.status = "RUNNING"
        start = time.time()
        agent = self._get_agent_for_node(node.role_profile)

        # Build context from dependencies
        dep_contexts = []
        for dep in node.depends_on:
            if dep in context and context[dep]:
                dep_contexts.append(f"--- Output from Dependency [{dep}] ---\n{context[dep][:1000]}")

        full_prompt = f"Task: {node.title}\nGoal Context: {self.goal}\n\nInstructions:\n{node.prompt}"
        if dep_contexts:
            full_prompt += "\n\n" + "\n\n".join(dep_contexts)

        resp: AgentResponse = agent.think(full_prompt)
        node.duration = round(time.time() - start, 3)

        if resp.success and resp.content:
            node.status = "COMPLETED"
            node.result = resp.content
        else:
            node.status = "FAILED"
            node.error = getattr(resp, "error_message", "") or getattr(resp, "error", "") or "Agent generation failed."

        return node

    def execute_parallel(self, max_workers: int = 4) -> DAGResult:
        """Executes independent topological batches concurrently."""
        batches = self.get_topological_batches()
        context: Dict[str, str] = {}
        start_dag = time.time()
        completed_count = 0
        failed_count = 0

        for batch in batches:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batch) or 1)) as executor:
                future_to_node = {
                    executor.submit(self._execute_node, node, context): node
                    for node in batch
                }
                for future in as_completed(future_to_node):
                    try:
                        node = future.result()
                    except Exception as e:
                        node = future_to_node[future]
                        node.status = "FAILED"
                        node.error = f"Execution error: {str(e)}"
                    if node.status == "COMPLETED":
                        completed_count += 1
                        context[node.id] = node.result
                    else:
                        failed_count += 1

        total_time = round(time.time() - start_dag, 3)
        return DAGResult(
            success=(failed_count == 0),
            goal=self.goal,
            total_tasks=len(self.nodes),
            completed_tasks=completed_count,
            failed_tasks=failed_count,
            total_time=total_time,
            nodes=self.nodes,
            mermaid_graph=self.to_mermaid()
        )

    @classmethod
    def build_default_dag_for_goal(cls, goal: str, model: str = "auto") -> "TaskDAG":
        """Constructs an enterprise 5-node parallel development DAG."""
        dag = cls(goal=goal, model=model)

        # 1. Product Requirements (Root)
        dag.add_task(TaskNode(
            id="task_prd",
            title="Product Requirements & Acceptance Criteria",
            role_profile="agent_product_manager",
            prompt="Draft PRD and acceptance criteria for this goal."
        ))

        # 2. Architecture (Depends on PRD)
        dag.add_task(TaskNode(
            id="task_arch",
            title="Low-Level Architecture & Contracts",
            role_profile="agent_software_designer",
            prompt="Specify class models and interface contracts based on PRD.",
            depends_on=["task_prd"]
        ))

        # 3. Core Engine Implementation (Depends on Architecture)
        dag.add_task(TaskNode(
            id="task_core_impl",
            title="Core Engine Implementation",
            role_profile="agent_sde",
            prompt="Implement clean, modular core Python code based on architecture.",
            depends_on=["task_arch"]
        ))

        # 4. Security Audit (Parallel with QA, depends on Core Implementation)
        dag.add_task(TaskNode(
            id="task_sec_audit",
            title="Security & Threat Audit",
            role_profile="agent_security_engineer",
            prompt="Audit core implementation for vulnerabilities, injection, and resource limits.",
            depends_on=["task_core_impl"]
        ))

        # 5. QA & Test Suite (Parallel with Security, depends on Core Implementation)
        dag.add_task(TaskNode(
            id="task_qa_tests",
            title="QA Test Automation Suite",
            role_profile="agent_test_automation_engineer",
            prompt="Generate comprehensive unittest test cases for core implementation.",
            depends_on=["task_core_impl"]
        ))

        return dag
