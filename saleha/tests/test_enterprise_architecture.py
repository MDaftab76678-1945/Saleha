"""
Unit & Integration Tests for Enterprise Architecture Upgrades:
- Swarm Checkpoint Store & Session Resume
- Type-Safe Agent Output Schema Contracts
- Sandboxed Worker Pool Isolation
- Micro-Kernel Plugin Manifest Engine
"""

import time
import unittest
from saleha.core.swarm_checkpoint_store import SwarmCheckpointStore, SwarmCheckpoint
from saleha.core.swarm_pipeline_engine import SwarmPipelineEngine
from saleha.core.agent_contracts import (
    ArchitectOutputContract,
    CoderOutputContract,
    SecurityOutputContract,
    QAOutputContract,
    ReviewerOutputContract,
    FinOpsOutputContract,
    DesignerOutputContract,
    DataEngineerOutputContract,
    DevOpsOutputContract,
)
from saleha.core.agent_worker_pool import AgentWorkerPool
from saleha.core.plugin_manifest import PluginManifestEngine, SalehaPluginManifest, PluginAgentSpec


class SwarmCheckpointStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = SwarmCheckpointStore(storage_dir=".saleha/test_cp_tmp")

    def tearDown(self):
        for cp in self.store.list_checkpoints():
            self.store.delete_checkpoint(cp.execution_id)

    def test_save_and_retrieve_checkpoint(self):
        cp = SwarmCheckpoint(
            execution_id="test_exec_01",
            goal="Synthesize caching service",
            role_sequence=["Architect", "Coder", "QA"],
            completed_stages=[{"stage_id": "s1", "role": "Architect"}],
            state_payload={"adr_title": "ADR: Cache"},
            status="in_progress"
        )
        self.store.save_checkpoint(cp)

        retrieved = self.store.get_checkpoint("test_exec_01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.goal, "Synthesize caching service")
        self.assertEqual(len(retrieved.completed_stages), 1)
        self.assertEqual(retrieved.state_payload.get("adr_title"), "ADR: Cache")

    def test_list_and_delete_checkpoints(self):
        cp1 = SwarmCheckpoint(execution_id="cp1", goal="Goal 1", role_sequence=["Coder"])
        cp2 = SwarmCheckpoint(execution_id="cp2", goal="Goal 2", role_sequence=["QA"])
        self.store.save_checkpoint(cp1)
        self.store.save_checkpoint(cp2)

        checkpoints = self.store.list_checkpoints()
        self.assertTrue(len(checkpoints) >= 2)

        self.assertTrue(self.store.delete_checkpoint("cp1"))
        self.assertIsNone(self.store.get_checkpoint("cp1"))


class SessionResumeIntegrationTests(unittest.TestCase):
    def test_execute_and_resume_swarm(self):
        engine = SwarmPipelineEngine()
        res = engine.execute_swarm("Synthesize resilient task runner in Python")
        self.assertTrue(res.success)
        self.assertTrue(res.execution_id)

        # Resume using existing checkpoint
        resumed = engine.resume_swarm(res.execution_id)
        self.assertTrue(resumed.success)
        self.assertTrue(resumed.resumed_from_checkpoint)
        self.assertEqual(resumed.goal, res.goal)
        self.assertEqual(resumed.final_code, res.final_code)


class AgentContractsTests(unittest.TestCase):
    def test_architect_contract_validation(self):
        c = ArchitectOutputContract(adr_title="ADR: Microservices", pattern="Hexagonal", components=["Auth", "Billing"])
        self.assertTrue(c.validate())

        bad_c = ArchitectOutputContract(adr_title="", pattern="", components=[])
        self.assertFalse(bad_c.validate())

    def test_coder_contract_ast_validation(self):
        valid_code = "class Cache:\n    def get(self, key):\n        return None\n"
        c = CoderOutputContract(source_code=valid_code)
        self.assertTrue(c.validate())
        self.assertIn("Cache", c.classes_defined)
        self.assertIn("get", c.functions_defined)

        invalid_syntax = "class Broken { def bad: "
        bad_c = CoderOutputContract(source_code=invalid_syntax)
        self.assertFalse(bad_c.validate())

    def test_security_and_qa_contracts(self):
        sec = SecurityOutputContract(is_secure=True, vulnerabilities_found=[])
        self.assertTrue(sec.validate())

        qa = QAOutputContract(framework="pytest", test_code="assert 1 == 1", test_case_count=1)
        self.assertTrue(qa.validate())

        rev = ReviewerOutputContract(approved=True, score=9.5, feedback="LGTM")
        self.assertTrue(rev.validate())

        fin = FinOpsOutputContract(original_tokens=1000, optimized_tokens=500, token_savings_pct=50.0)
        self.assertTrue(fin.validate())


class AgentWorkerPoolTests(unittest.TestCase):
    def setUp(self):
        self.pool = AgentWorkerPool(max_workers=2)

    def tearDown(self):
        self.pool.shutdown(wait=False)

    def test_worker_pool_executes_task_successfully(self):
        def add(a: int, b: int) -> int:
            return a + b

        res = self.pool.execute_task("task_01", add, 10, 20)
        self.assertTrue(res.success)
        self.assertEqual(res.result, 30)
        self.assertGreaterEqual(res.execution_time_ms, 0.0)

    def test_worker_pool_handles_timeout(self):
        def slow_fn():
            time.sleep(0.5)
            return "done"

        res = self.pool.execute_task("slow_task", slow_fn, timeout_sec=0.1)
        self.assertFalse(res.success)
        self.assertIn("timed out", res.error_message.lower())


class PluginManifestEngineTests(unittest.TestCase):
    def test_register_and_query_plugin_manifest(self):
        engine = PluginManifestEngine(plugins_dir=".saleha/test_plugins_tmp")
        manifest = SalehaPluginManifest(
            plugin_id="plugin-ml-optimizer",
            name="ML Optimizer Plugin",
            version="1.0.0",
            author="DeepMind Team",
            agents=[
                PluginAgentSpec(
                    name="MLOpsSpecialistAgent",
                    role="MLOps",
                    description="Automated model quantization and ONNX exporting",
                    entrypoint="mlops_agent:MLOpsSpecialistAgent"
                )
            ]
        )
        engine.register_plugin_manifest(manifest)

        p = engine.get_plugin("plugin-ml-optimizer")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "ML Optimizer Plugin")
        self.assertEqual(len(p.agents), 1)
        self.assertEqual(p.agents[0].role, "MLOps")


if __name__ == "__main__":
    unittest.main()
