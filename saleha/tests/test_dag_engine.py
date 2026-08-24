import unittest
import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from saleha.core.dag_engine import TaskDAG, TaskNode, DAGResult
from saleha.cli.commands import cli


class DAGTests(unittest.TestCase):
    def test_topological_batching_layers(self):
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

    def test_mermaid_graph_generation(self):
        dag = TaskDAG.build_default_dag_for_goal("Build Microservice")
        mermaid = dag.to_mermaid()
        self.assertIn("flowchart TD", mermaid)
        self.assertIn("task_prd", mermaid)
        self.assertIn("task_core_impl", mermaid)
        self.assertIn("task_sec_audit", mermaid)

    def test_dag_parallel_execution_mock(self):
        dag = TaskDAG.build_default_dag_for_goal("Build Rate Limiter")
        with patch.object(dag, "_get_agent_for_node") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.think.return_value = MagicMock(success=True, content="Artifact Output")
            mock_get_agent.return_value = mock_agent

            res: DAGResult = dag.execute_parallel(max_workers=2)
            self.assertTrue(res.success)
            self.assertEqual(res.completed_tasks, 5)
            self.assertEqual(res.failed_tasks, 0)

    def test_cli_dag_json_output(self):
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

