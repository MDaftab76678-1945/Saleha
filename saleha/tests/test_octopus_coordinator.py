"""Unit tests for OctopusCoordinator and 9-Brain Multi-Agent Engine."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from saleha.core.harness.code_executor import ExecutionResult
from saleha.core.octopus_coordinator import (
    ArmBrainOutput,
    ArmBrainRole,
    OctopusCoordinator,
    OctopusExecutionResult,
    SynapticBlackboard,
)
from saleha.core.swarm.agent_message_bus import AgentMessageBus
from saleha.core.swarm.agent_worker_pool import AgentWorkerPool
from saleha.tests.swarm_stubs import GOOD_CODE, stub_agents


class OctopusCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = AgentMessageBus()
        self.worker_pool = AgentWorkerPool(max_workers=4)
        self.coordinator = OctopusCoordinator(
            model="mock",
            worker_pool=self.worker_pool,
            bus=self.bus,
            timeout_sec=30.0,
        )
        # Real code and tests for every run: model="mock" reaches no model,
        # and these tests used to pass only because the coordinator hid the
        # Coder's failure behind a `def execute(): return True` placeholder.
        stubs = stub_agents()
        stubs.__enter__()
        self.addCleanup(stubs.__exit__, None, None, None)

    def tearDown(self) -> None:
        self.worker_pool.shutdown(wait=False)

    def test_octopus_arm_roles_enum(self) -> None:
        expected_roles = {
            "planner",
            "architect",
            "coder",
            "security",
            "qa",
            "sre",
            "critic",
            "toolforge",
        }
        actual_roles = {role.value for role in ArmBrainRole}
        self.assertEqual(actual_roles, expected_roles)
        self.assertEqual(len(ArmBrainRole), 8)

    def test_synaptic_blackboard_thread_safety(self) -> None:
        blackboard = SynapticBlackboard(goal="Test Thread Safety")
        out1 = ArmBrainOutput(
            brain_role="planner",
            brain_name="PlannerBrain",
            status="success",
            summary="Plan complete",
            duration_ms=10.5,
        )
        out2 = ArmBrainOutput(
            brain_role="architect",
            brain_name="ArchitectBrain",
            status="success",
            summary="ADR complete",
            duration_ms=12.1,
        )
        blackboard.record_brain_output(out1)
        blackboard.record_brain_output(out2)
        self.assertEqual(len(blackboard.brain_outputs), 2)
        self.assertIn("planner", blackboard.brain_outputs)
        self.assertIn("architect", blackboard.brain_outputs)

    def test_octopus_coordinate_end_to_end_mock(self) -> None:
        events_captured = []
        self.bus.subscribe("*", lambda e: events_captured.append(e))

        dispatched_brains = []

        def on_brain(out: ArmBrainOutput) -> None:
            dispatched_brains.append(out.brain_role)

        result: OctopusExecutionResult = self.coordinator.coordinate(
            goal="Build a thread-safe token bucket rate limiter",
            callback=on_brain,
        )

        self.assertIsInstance(result, OctopusExecutionResult)
        self.assertTrue(result.execution_id)
        self.assertEqual(result.goal, "Build a thread-safe token bucket rate limiter")
        self.assertEqual(result.final_code, GOOD_CODE)
        self.assertTrue(result.success, result.summary_report)
        self.assertTrue(result.tests_ran and result.tests_passed)
        self.assertIsNone(result.resilience_score)
        self.assertTrue(result.total_duration_ms >= 0.0)

        # All 8 peripheral arm brains must be present in brain_outputs
        self.assertEqual(len(result.brain_outputs), 8)
        for role in ArmBrainRole:
            self.assertIn(role.value, result.brain_outputs)
            self.assertEqual(result.brain_outputs[role.value].status, "success")

        # Verify event bus traffic
        event_types = [e.event_type for e in events_captured]
        self.assertIn("octopus_brain_dispatched", event_types)
        self.assertIn("octopus_brain_completed", event_types)
        self.assertIn("octopus_synthesis_completed", event_types)

    def test_octopus_physical_sandbox_test_failure_honesty(self) -> None:
        """When sandbox test execution fails, tests_passed must be False and success False."""
        fake_failing_exec = ExecutionResult(
            success=False,
            output="",
            error="AssertionError: Expected 10 requests allowed, got 0",
            exit_code=1,
        )

        with patch("saleha.core.harness.code_executor.CodeExecutor.execute", return_value=fake_failing_exec):
            result = self.coordinator.coordinate(
                goal="Implement failing rate limiter",
            )
            self.assertFalse(result.tests_passed)
            self.assertFalse(result.success)
            self.assertIn("AssertionError", result.summary_report)

    def test_octopus_security_hardening_conflict_resolution(self) -> None:
        """When security arm finds dangerous code, it hardens it and logs conflict resolution."""
        events_captured = []
        self.bus.subscribe("octopus_conflict_resolved", lambda e: events_captured.append(e))

        from saleha.agents.security_guard import SecurityAuditResult

        fake_audit = SecurityAuditResult(
            is_secure=False,
            vulnerabilities_found=["CWE-78: OS Command Injection"],
            cwe_identifiers=["CWE-78"],
            hardened_code="def safe_exec():\n    return True\n",
            audit_report="Security alert report",
            model_used="mock",
        )

        with patch("saleha.agents.security_guard.SecurityGuardAgent.audit_and_harden", return_value=fake_audit):
            result = self.coordinator.coordinate(
                goal="Sanitize dangerous input",
            )
            self.assertFalse(result.security_clean)
            self.assertFalse(result.success)
            self.assertEqual(len(events_captured), 1)
            self.assertEqual(events_captured[0].event_type, "octopus_conflict_resolved")
            # The untested regex patch is a suggestion; the returned code is
            # the code QA actually tested.
            self.assertEqual(result.final_code, GOOD_CODE)

    def test_no_code_means_no_success_and_checks_not_run(self) -> None:
        with stub_agents(code=None):
            result = self.coordinator.coordinate(goal="Build a rate limiter")
        self.assertFalse(result.success)
        self.assertFalse(result.code_generated)
        self.assertFalse(result.tests_ran)
        self.assertFalse(result.security_checked)
        self.assertEqual(result.final_code, "")
        self.assertIn("Code: NOT GENERATED", result.summary_report)
        self.assertEqual(result.brain_outputs["coder"].status, "failed")
        self.assertEqual(result.brain_outputs["qa"].status, "failed")
        self.assertIn("no generated code", result.brain_outputs["qa"].summary)

    def test_crashed_arm_is_not_a_pass(self) -> None:
        # The blackboard used to start tests_passed=True, so a QA arm that
        # raised left "passed" behind.
        with patch("saleha.agents.qa_lead.QALeadAgent.generate_test_suite",
                   side_effect=RuntimeError("qa crashed")):
            result = self.coordinator.coordinate(goal="Build a rate limiter")
        self.assertFalse(result.tests_passed)
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
