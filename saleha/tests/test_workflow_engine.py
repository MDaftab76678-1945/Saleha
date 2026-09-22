"""
Saleha Workflow Engine (SalehaFlow) Comprehensive Test Suite.

Verifies:
1. Topological DAG batching, parallel execution, and cascading skip behavior.
2. Circular dependency detection and missing dependency validation.
3. Active-Inference Self-Healing on schema drift (KeyError / TypeError).
4. Formally verified AST-audited sandbox execution & security violation rejection.
5. Byzantine Fault Tolerant (BFT) multi-agent quorum consensus.
6. Codebase-native and system triggers (Cron, Webhook, TestFailure, Complexity).
7. Declarative Pythonic DSL and visual JSON DAG serialization.
"""

from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any, Dict

from saleha.core.workflow.nodes import (
    ActionNode,
    CodeNode,
    ConditionNode,
    NodeStatus,
    WorkflowExecutionContext,
)
from saleha.core.workflow.self_healing_node import SelfHealingNode
from saleha.core.workflow.verified_sandbox_node import (
    SecurityViolationError,
    VerifiedSandboxNode,
)
from saleha.core.workflow.bft_consensus_node import BFTConsensusNode
from saleha.core.workflow.triggers import (
    ComplexityTrigger,
    CronTrigger,
    TestFailureTrigger,
    WebhookTrigger,
)
from saleha.core.workflow.workflow_engine import (
    WorkflowDAG,
    WorkflowExecutionResult,
)
from saleha.core.workflow.dsl import (
    WorkflowBuilder,
    get_workflow,
    list_registered_workflows,
    register_workflow,
    step,
    workflow,
)


class TestSalehaFlowEngine(unittest.TestCase):
    """Unit tests for the SalehaFlow autonomous workflow system."""

    def test_topological_execution_and_data_piping(self) -> None:
        """Verifies diamond DAG execution (A -> B, A -> C, B & C -> D) and output propagation."""
        dag = WorkflowDAG(name="Diamond Pipeline")

        node_a = ActionNode("A", "Source", lambda inp, ctx: {"val": 10})
        node_b = ActionNode("B", "Multiply", lambda inp, ctx: {"b_val": inp["val"] * 2}, depends_on=["A"])
        node_c = ActionNode("C", "Add", lambda inp, ctx: {"c_val": inp["val"] + 5}, depends_on=["A"])
        node_d = ActionNode(
            "D",
            "Combine",
            lambda inp, ctx: {"total": inp["b_val"] + inp["c_val"]},
            depends_on=["B", "C"],
        )

        dag.add_node(node_a).add_node(node_b).add_node(node_c).add_node(node_d)

        batches = dag.get_topological_batches()
        self.assertEqual(len(batches), 3)
        self.assertEqual([n.id for n in batches[0]], ["A"])
        self.assertEqual(sorted([n.id for n in batches[1]]), ["B", "C"])
        self.assertEqual([n.id for n in batches[2]], ["D"])

        result = dag.execute()
        self.assertTrue(result.success)
        self.assertEqual(len(result.completed_nodes), 4)
        self.assertEqual(result.node_results["D"]["outputs"]["total"], 35)

    def test_circular_dependency_rejection(self) -> None:
        """Proves circular graphs are rejected with a clear ValueError."""
        dag = WorkflowDAG(name="Cycle")
        n1 = ActionNode("n1", "Node 1", lambda inp, ctx: {}, depends_on=["n2"])
        n2 = ActionNode("n2", "Node 2", lambda inp, ctx: {}, depends_on=["n1"])
        dag.add_node(n1).add_node(n2)

        with self.assertRaises(ValueError) as cm:
            dag.get_topological_batches()
        self.assertIn("Circular dependency detected", str(cm.exception))

    def test_missing_dependency_rejection(self) -> None:
        """Proves dependencies on non-existent nodes raise KeyError."""
        dag = WorkflowDAG(name="Missing Dep")
        n1 = ActionNode("n1", "Node 1", lambda inp, ctx: {}, depends_on=["ghost_node"])
        dag.add_node(n1)

        with self.assertRaises(KeyError) as cm:
            dag.get_topological_batches()
        self.assertIn("ghost_node", str(cm.exception))

    def test_cascading_failure_skips_downstream(self) -> None:
        """Proves downstream nodes are marked SKIPPED if an upstream node fails."""
        dag = WorkflowDAG(name="Failure Cascade")

        def bad_action(inp, ctx):
            raise RuntimeError("Database connection refused")

        n1 = ActionNode("n1", "Failing Node", bad_action)
        n2 = ActionNode("n2", "Downstream Node", lambda inp, ctx: {"ok": True}, depends_on=["n1"])
        dag.add_node(n1).add_node(n2)

        result = dag.execute()
        self.assertFalse(result.success)
        self.assertIn("n1", result.failed_nodes)
        self.assertIn("n2", result.skipped_nodes)
        self.assertEqual(result.node_results["n2"]["status"], "SKIPPED")

    def test_self_healing_recovers_from_schema_drift(self) -> None:
        """
        Demonstrates superior self-healing over n8n:
        Upstream renamed key 'account_id' to 'accountId'.
        Inner node expects 'account_id' and raises KeyError.
        SelfHealingNode intercepts KeyError, applies fuzzy schema repair, and recovers!
        """
        dag = WorkflowDAG(name="Self-Healing Demo")

        # Upstream returns drifted schema
        source = ActionNode("source", "API Source", lambda inp, ctx: {"accountId": "ACC-9988"})

        # Consumer node strictly accesses old key name
        def consumer_fn(inp, ctx):
            return {"verified_account": inp["account_id"].lower()}

        raw_consumer = ActionNode("consumer", "Legacy Consumer", consumer_fn, depends_on=["source"])
        healing_consumer = SelfHealingNode(raw_consumer, max_repair_attempts=2)

        dag.add_node(source).add_node(healing_consumer)

        result = dag.execute()
        self.assertTrue(result.success)
        self.assertIn("consumer", result.healed_nodes)
        self.assertEqual(
            result.node_results["consumer"]["outputs"]["verified_account"],
            "acc-9988",
        )
        self.assertTrue(result.node_results["consumer"]["metadata"]["healed"])

    def test_self_healing_does_not_invent_missing_keys(self) -> None:
        dag = WorkflowDAG(name="No Invented Keys")
        source = ActionNode("source", "Source", lambda inp, ctx: {"unrelated": 1})
        consumer = ActionNode(
            "consumer", "Consumer", lambda inp, ctx: {"x": inp["account_id"]}, depends_on=["source"]
        )
        dag.add_node(source).add_node(SelfHealingNode(consumer, max_repair_attempts=2))

        result = dag.execute()

        self.assertFalse(result.success)
        self.assertIn("consumer", result.failed_nodes)

    def test_code_node_runs_out_of_process(self) -> None:
        import os

        node = CodeNode("pid", "Pid", code_str="import os\noutputs = {'pid': os.getpid()}")
        ctx = WorkflowExecutionContext(workflow_id="t", execution_id="e")

        self.assertNotEqual(node.execute(ctx)["pid"], os.getpid())

    def test_verified_sandbox_enforces_timeout(self) -> None:
        node = VerifiedSandboxNode("spin", "Spin", code_str="while True:\n    pass", timeout_sec=1.0)
        ctx = WorkflowExecutionContext(workflow_id="t", execution_id="e")

        with self.assertRaises(RuntimeError) as cm:
            node.execute(ctx)
        self.assertIn("TIMEOUT", str(cm.exception))

    def test_verified_sandbox_blocks_forbidden_imports(self) -> None:
        """Proves malicious code with unauthorized syscalls/imports is blocked before execution."""
        malicious_code = """
import subprocess
outputs = {"pwned": True}
"""
        node = VerifiedSandboxNode("exploit", "Attack Vector", code_str=malicious_code)
        ctx = WorkflowExecutionContext(workflow_id="test", execution_id="test_exec")

        with self.assertRaises(SecurityViolationError) as cm:
            node.execute(ctx)
        self.assertIn("Forbidden import: 'subprocess'", str(cm.exception))

    def test_verified_sandbox_allows_safe_computations(self) -> None:
        """Proves legitimate mathematical and transform logic executes cleanly inside sandbox."""
        safe_code = """
data = inputs.get('numbers', [1, 2, 3, 4, 5])
outputs = {
    'sum': sum(data),
    'max': max(data),
    'count': len(data),
}
"""
        node = VerifiedSandboxNode("safe_math", "Safe Math", code_str=safe_code)
        ctx = WorkflowExecutionContext(workflow_id="test", execution_id="test_exec")
        ctx.set_output("root", {"numbers": [10, 20, 30]})
        node.depends_on = ["root"]

        out = node.execute(ctx)
        self.assertEqual(out["sum"], 60)
        self.assertEqual(out["max"], 30)
        self.assertEqual(out["count"], 3)

    def test_bft_consensus_node_reaches_quorum(self) -> None:
        """Proves multi-agent BFT voting ratifies an outcome when quorum is satisfied."""
        voter_1 = lambda inp, ctx: "APPROVE_DEPLOYMENT"
        voter_2 = lambda inp, ctx: "APPROVE_DEPLOYMENT"
        voter_3 = lambda inp, ctx: "REJECT_DEPLOYMENT"

        bft = BFTConsensusNode(
            "consensus_gate",
            "Production Gate",
            voters=[voter_1, voter_2, voter_3],
            quorum_fraction=0.66,
        )
        ctx = WorkflowExecutionContext(workflow_id="test", execution_id="test_exec")
        out = bft.execute(ctx)

        self.assertEqual(out["decision"], "APPROVE_DEPLOYMENT")
        self.assertGreaterEqual(out["confidence"], 0.66)
        self.assertEqual(out["vote_count"], 2)
        self.assertEqual(out["total_voters"], 3)

    def test_bft_consensus_node_rejects_hallucination_without_quorum(self) -> None:
        """Proves multi-agent BFT voting rejects disjoint/split votes without quorum."""
        voter_1 = lambda inp, ctx: "OPTION_A"
        voter_2 = lambda inp, ctx: "OPTION_B"
        voter_3 = lambda inp, ctx: "OPTION_C"

        bft = BFTConsensusNode(
            "split_gate",
            "Split Gate",
            voters=[voter_1, voter_2, voter_3],
            quorum_fraction=0.66,
        )
        ctx = WorkflowExecutionContext(workflow_id="test", execution_id="test_exec")

        with self.assertRaises(RuntimeError) as cm:
            bft.execute(ctx)
        self.assertIn("failed to reach quorum", str(cm.exception))

    def test_triggers_evaluation(self) -> None:
        """Tests Cron, Webhook, TestFailure, and Complexity triggers."""
        # 1. Cron Trigger
        cron_trig = CronTrigger("cron_job", "Hourly Cron", "0 * * * *")
        fixed_dt = datetime(2026, 9, 22, 14, 0, 0)
        self.assertTrue(cron_trig.is_triggered({"timestamp": fixed_dt}))
        wrong_dt = datetime(2026, 9, 22, 14, 15, 0)
        self.assertFalse(cron_trig.is_triggered({"timestamp": wrong_dt}))

        # 2. Webhook Trigger
        webhook_trig = WebhookTrigger("hook", "GitHub Webhook", path="/hooks/github", secret_token="sec123")
        self.assertTrue(webhook_trig.is_triggered({"path": "/hooks/github", "token": "sec123"}))
        self.assertFalse(webhook_trig.is_triggered({"path": "/hooks/github", "token": "wrong"}))
        self.assertFalse(webhook_trig.is_triggered({"path": "/other"}))

        # 3. Test Failure Trigger
        test_trig = TestFailureTrigger("qa_fail", "Auto-Heal Trigger")
        self.assertTrue(test_trig.is_triggered({"exit_code": 1, "failed_tests": 2}))
        self.assertFalse(test_trig.is_triggered({"exit_code": 0, "failed_tests": 0}))

        # 4. Complexity Trigger
        comp_trig = ComplexityTrigger("cc_gate", "Complexity Gate", max_allowed_complexity=10.0)
        self.assertTrue(comp_trig.is_triggered({"complexity_score": 14.5}))
        self.assertFalse(comp_trig.is_triggered({"complexity_score": 6.2}))

    def test_workflow_builder_and_registry(self) -> None:
        """Verifies fluent WorkflowBuilder API and global registry."""
        builder = WorkflowBuilder(name="Fluent Pipeline", description="Testing builder")
        dag = (
            builder.add_action("fetch", "Fetch Records", lambda inp, ctx: {"items": [1, 2, 3]})
            .add_action("process", "Process", lambda inp, ctx: {"count": len(inp["items"])}, depends_on=["fetch"])
            .build(register=True)
        )

        self.assertEqual(dag.name, "Fluent Pipeline")
        self.assertIn("fetch", dag.nodes)
        self.assertIn("process", dag.nodes)

        # Retrieve from registry
        retrieved = get_workflow("Fluent Pipeline")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.workflow_id, dag.workflow_id)

    def test_visual_dag_serialization(self) -> None:
        """Verifies visual JSON DAG serialization and Mermaid export."""
        dag = WorkflowDAG(name="Visual DAG", description="For Web Studio")
        n1 = ActionNode("start", "Start Node", lambda inp, ctx: {})
        n2 = ActionNode("end", "End Node", lambda inp, ctx: {}, depends_on=["start"])
        dag.add_node(n1).add_node(n2)

        data = dag.to_dict()
        self.assertEqual(data["name"], "Visual DAG")
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["connections"]), 1)
        self.assertEqual(data["connections"][0], {"from": "start", "to": "end"})

        # Action nodes hold Python callables; loading them from JSON must fail
        # rather than come back as pass-through stand-ins.
        with self.assertRaises(ValueError):
            WorkflowDAG.from_dict(data)

        code_dag = WorkflowDAG.from_dict({
            "name": "Code DAG",
            "nodes": [
                {"id": "start", "type": "code", "config": {"code": "outputs = {'n': 2}"}},
                {"id": "end", "type": "code", "depends_on": ["start"],
                 "config": {"code": "outputs = {'n': inputs['n'] * 3}"}},
            ],
        })
        self.assertEqual(code_dag.nodes["end"].depends_on, ["start"])
        self.assertEqual(code_dag.execute().node_results["end"]["outputs"], {"n": 6})

        # Mermaid output
        mermaid = dag.to_mermaid()
        self.assertIn("flowchart TD", mermaid)
        self.assertIn("start --> end", mermaid)


if __name__ == "__main__":
    unittest.main()
