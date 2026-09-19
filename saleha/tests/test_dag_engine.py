"""
Tests for Saleha Core TaskDAG Engine (saleha/core/dag_engine.py).

Verifies topological batching, missing dependency detection, cycle detection,
cascading failure skipping, offline executor hooks, and cp1252-safe text badges.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from saleha.cli.commands import cli
from saleha.core.dag_engine import DAGResult, TaskDAG, TaskNode


class DAGTopologicalSortingTests(unittest.TestCase):
    def test_topological_batching_layers(self) -> None:
        dag = TaskDAG(goal="Build Distributed Cache")
        n1 = TaskNode("n1", "Requirements", "agent_product_manager", "prd")
        n2 = TaskNode("n2", "Design", "agent_software_designer", "lld", depends_on=["n1"])
        n3 = TaskNode("n3", "Core Code", "agent_sde", "code", depends_on=["n2"])
        n4 = TaskNode("n4", "Security", "agent_security_engineer", "audit", depends_on=["n3"])
        n5 = TaskNode("n5", "QA Tests", "agent_tester", "test", depends_on=["n3"])

        dag.add_task(n1)
        dag.add_task(n2)
        dag.add_task(n3)
        dag.add_task(n4)
        dag.add_task(n5)

        batches = dag.get_topological_batches()
        self.assertEqual(len(batches), 4)
        self.assertEqual([n.id for n in batches[0]], ["n1"])
        self.assertEqual([n.id for n in batches[1]], ["n2"])
        self.assertEqual([n.id for n in batches[2]], ["n3"])
        # Batch 4 should have both n4 and n5 in parallel!
        self.assertEqual(set(n.id for n in batches[3]), {"n4", "n5"})

    def test_missing_dependency_raises_key_error(self) -> None:
        dag = TaskDAG(goal="Broken DAG")
        n1 = TaskNode("n1", "Task 1", "agent_sde", "run", depends_on=["non_existent_node"])
        dag.add_task(n1)

        with self.assertRaises(KeyError) as ctx:
            dag.get_topological_batches()
        self.assertIn("non_existent_node", str(ctx.exception))

    def test_circular_dependency_raises_value_error(self) -> None:
        dag = TaskDAG(goal="Cyclic DAG")
        n1 = TaskNode("n1", "Task 1", "agent_sde", "prompt1", depends_on=["n2"])
        n2 = TaskNode("n2", "Task 2", "agent_sde", "prompt2", depends_on=["n1"])
        dag.add_task(n1)
        dag.add_task(n2)

        with self.assertRaises(ValueError) as ctx:
            dag.get_topological_batches()
        self.assertIn("Circular dependency detected", str(ctx.exception))


class DAGExecutionTests(unittest.TestCase):
    def test_mermaid_graph_generation_uses_text_badges(self) -> None:
        dag = TaskDAG.build_default_dag_for_goal("Build Microservice")
        mermaid = dag.to_mermaid()
        self.assertIn("flowchart TD", mermaid)
        self.assertIn("[GOAL]", mermaid)
        self.assertIn("[PENDING]", mermaid)
        self.assertIn("task_prd", mermaid)
        self.assertIn("task_core_impl", mermaid)
        self.assertIn("task_sec_audit", mermaid)
        # Ensure no non-ASCII emojis in the graph
        self.assertTrue(mermaid.isascii())

    def test_dag_parallel_execution_mock_agent(self) -> None:
        dag = TaskDAG.build_default_dag_for_goal("Build Rate Limiter")
        with patch.object(dag, "_get_agent_for_node") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.think.return_value = MagicMock(success=True, content="Artifact Output")
            mock_get_agent.return_value = mock_agent

            res: DAGResult = dag.execute_parallel(max_workers=2)
            self.assertTrue(res.success)
            self.assertEqual(res.completed_tasks, 5)
            self.assertEqual(res.failed_tasks, 0)
            self.assertEqual(res.skipped_tasks, 0)

    def test_custom_executor_hook_execution(self) -> None:
        dag = TaskDAG.build_default_dag_for_goal("Custom Hook Goal")

        def mock_executor(node: TaskNode, ctx: dict[str, str]) -> str:
            return f"Processed output for {node.id}"

        res = dag.execute_parallel(max_workers=2, executor_fn=mock_executor)
        self.assertTrue(res.success)
        self.assertEqual(res.completed_tasks, 5)
        self.assertEqual(res.failed_tasks, 0)
        self.assertEqual(res.skipped_tasks, 0)
        self.assertEqual(res.nodes["task_prd"].result, "Processed output for task_prd")
        self.assertEqual(res.nodes["task_prd"].status, "COMPLETED")

    def test_dependency_failure_cascades_and_skips_downstream(self) -> None:
        dag = TaskDAG(goal="Cascade Failure Test")
        n1 = TaskNode("n1", "Step 1", "agent_sde", "prompt")
        n2 = TaskNode("n2", "Step 2", "agent_sde", "prompt", depends_on=["n1"])
        n3 = TaskNode("n3", "Step 3", "agent_sde", "prompt", depends_on=["n2"])
        dag.add_task(n1)
        dag.add_task(n2)
        dag.add_task(n3)

        def failing_executor(node: TaskNode, ctx: dict[str, str]) -> str:
            if node.id == "n1":
                raise RuntimeError("Hardware crash on step 1")
            return "OK"

        res = dag.execute_parallel(max_workers=2, executor_fn=failing_executor)
        self.assertFalse(res.success)
        self.assertEqual(res.completed_tasks, 0)
        self.assertEqual(res.failed_tasks, 1)
        self.assertEqual(res.skipped_tasks, 2)
        self.assertEqual(res.nodes["n1"].status, "FAILED")
        self.assertEqual(res.nodes["n2"].status, "SKIPPED")
        self.assertEqual(res.nodes["n3"].status, "SKIPPED")
        self.assertIn("broken upstream dependencies: n1", res.nodes["n2"].error)

    def test_cli_dag_json_output(self) -> None:
        with patch("saleha.cli.commands.TaskDAG") as mock_dag_cls:
            mock_dag = MagicMock()
            mock_dag.nodes = {
                "t1": TaskNode("t1", "PRD", "pm", "p", status="COMPLETED", duration=0.1, result="done")
            }
            mock_dag.execute_parallel.return_value = DAGResult(
                success=True,
                goal="Build Cache",
                total_tasks=1,
                completed_tasks=1,
                failed_tasks=0,
                skipped_tasks=0,
                total_time=0.1,
                nodes=mock_dag.nodes,
                mermaid_graph="flowchart TD"
            )
            mock_dag_cls.build_default_dag_for_goal.return_value = mock_dag

            res = CliRunner().invoke(cli, ["dag", "Build Cache", "--json"])
            self.assertEqual(res.exit_code, 0)
            payload = json.loads(res.output)
            self.assertTrue(payload["success"])
            self.assertIn("t1", payload["tasks"])


if __name__ == "__main__":
    unittest.main()


