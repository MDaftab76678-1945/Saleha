"""
Unit tests for Specialized Orchestrators and New Agent Personas in Saleha v2.6.0
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from saleha.core.fast_inference import InferenceResult

from saleha.core.cloud_infra_orchestrator import CloudInfraOrchestrator, CloudInfraPlan
from saleha.core.multirepo_orchestrator import MultiRepoOrchestrator, MultiRepoSyncPlan
from saleha.core.silicon_circuit_orchestrator import SiliconCircuitOrchestrator, SiliconCircuitDesign
from saleha.core.debate_consensus_orchestrator import DebateConsensusOrchestrator, DebateVerdict


class SpecializedOrchestratorsTests(unittest.TestCase):

    def setUp(self):
        self.cloud = CloudInfraOrchestrator()
        self.multirepo = MultiRepoOrchestrator()
        self.silicon = SiliconCircuitOrchestrator()
        # The debate orchestrator now makes real model calls (it used to
        # return f-string templates and a hardcoded 0.948 confidence). Inject
        # a fake engine so this stays a unit test and does not need Ollama.
        fake = MagicMock()
        fake.run.side_effect = lambda req, **kw: InferenceResult(
            success=True,
            content="## Decision" + chr(10) + "Adopt ClickHouse for the event log.",
            tag=req.tag)
        fake.run_batch.side_effect = lambda reqs, **kw: [
            InferenceResult(success=True, content="critique of " + r.tag, tag=r.tag)
            for r in reqs]
        self.debate = DebateConsensusOrchestrator(inference=fake)

    def test_cloud_infra_orchestrator(self):
        plan: CloudInfraPlan = self.cloud.plan_and_generate_infra(
            goal="Deploy Scalable Redis Cluster on AWS",
            cloud_provider="aws",
            high_availability=True
        )
        self.assertIn("terraform {", plan.terraform_code)
        self.assertIn("apiVersion: apps/v1", plan.kubernetes_manifests)
        self.assertIn("replicaCount: 3", plan.helm_values)
        self.assertGreater(plan.finops_estimated_monthly_cost, 0)
        self.assertEqual(plan.cloud_provider, "aws")
        # `assertGreaterEqual(plan.security_score, 90)` used to be here. It
        # pinned a hardcoded 96 that came from no analysis of anything -- the
        # same shape of trap as the other tests that asserted fabricated
        # values. There is no score now, and the plan says it is a template.
        self.assertIsNone(plan.security_score)
        self.assertTrue(plan.is_template)
        self.assertTrue(plan.caveats)

    def test_cloud_plan_is_marked_as_a_template_not_a_design(self):
        """
        Measured: two unrelated goals produce byte-identical k8s manifests,
        helm values, IAM policy and CI/CD workflow. The Terraform differs only
        where the goal string is echoed.
        """
        a = self.cloud.plan_and_generate_infra(goal="Multi-region Postgres")
        b = self.cloud.plan_and_generate_infra(goal="Write a haiku about frogs")
        self.assertEqual(a.kubernetes_manifests, b.kubernetes_manifests)
        self.assertEqual(a.iam_policy_json, b.iam_policy_json)
        self.assertTrue(a.is_template)

    def test_non_aws_provider_is_reported_not_silently_wrong(self):
        """
        The Terraform is AWS whatever provider is asked for -- S3 backend,
        us-east-1, terraform-aws-modules/vpc/aws -- and `hashicorp/gcp` is not
        even a real provider address. It cannot `terraform init`.
        """
        plan = self.cloud.plan_and_generate_infra(goal="x", cloud_provider="gcp")
        self.assertTrue(plan.provider_mismatch)
        self.assertIn("AWS", plan.provider_mismatch)
        self.assertTrue(plan.terraform_code.startswith("# WARNING"))

    def test_aws_provider_has_no_mismatch_warning(self):
        plan = self.cloud.plan_and_generate_infra(goal="x", cloud_provider="aws")
        self.assertEqual(plan.provider_mismatch, "")
        self.assertFalse(plan.terraform_code.startswith("# WARNING"))

    def test_multirepo_orchestrator(self):
        repos = ["payments-api", "web-frontend", "notification-worker"]
        plan: MultiRepoSyncPlan = self.multirepo.plan_multirepo_sync(
            goal="Add UUID idempotency keys to payment requests",
            repos=repos
        )
        self.assertEqual(len(plan.affected_repos), 3)
        self.assertTrue(plan.is_atomic)
        self.assertIn("payments-api", plan.transforms)
        self.assertIn("web-frontend", plan.transforms)
        self.assertTrue(len(plan.migration_order) == 3)

    def test_silicon_circuit_orchestrator(self):
        design: SiliconCircuitDesign = self.silicon.synthesize_hardware_circuit(
            spec_goal="Design 32-bit pipelined ALU with arithmetic overflow flag",
            module_name="alu_core"
        )
        self.assertEqual(design.module_name, "saleha_alu_core")
        self.assertIn("module saleha_alu_core", design.verilog_rtl)
        self.assertIn("tb_saleha_alu_core", design.testbench_sv)
        self.assertIn("create_clock", design.timing_constraints_sdc)
        self.assertGreater(design.estimated_lut_count, 0)
        self.assertGreater(design.estimated_max_freq_mhz, 100.0)
        self.assertTrue(design.is_synthesizable)

    def test_debate_consensus_orchestrator(self):
        verdict: DebateVerdict = self.debate.conduct_architectural_debate(
            topic="PostgreSQL vs ClickHouse for 10M events/sec logging",
            options=["ClickHouse Columnar", "PostgreSQL TimescaleDB"],
            num_rounds=2
        )
        self.assertEqual(verdict.rounds_conducted, 2)
        self.assertEqual(len(verdict.rounds), 2)
        self.assertIn("Architecture Decision Record", verdict.adr_markdown)
        # Confidence is now measured participation, not the old 0.948 constant:
        # all 8 persona slots answered, so it is exactly 1.0.
        self.assertEqual(verdict.elo_confidence_score, 1.0)
        self.assertFalse(verdict.degraded)
        self.assertGreaterEqual(len(verdict.key_tradeoffs), 1)

    def test_new_agent_persona_files_exist_and_valid(self):
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        new_personas = [
            "agent_silicon_architect.md",
            "agent_cloud_resilience.md",
            "agent_quantum_symbolic.md",
            "agent_p2p_swarm_coordinator.md",
            "agent_neuro_optimizer.md",
            "agent_zero_day_hunter.md",
            "agent_spatial_3d_engine.md",
            "agent_embedded_firmware.md",
            "agent_finops_token_economist.md",
            "agent_semantic_data_pipeline.md",
        ]
        for persona_file in new_personas:
            p = skills_dir / persona_file
            self.assertTrue(p.exists(), f"Persona file missing: {persona_file}")
            content = p.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"Invalid YAML frontmatter in {persona_file}")
            self.assertIn("allowed_tools:", content)
            self.assertIn("goals:", content)


if __name__ == "__main__":
    unittest.main()
