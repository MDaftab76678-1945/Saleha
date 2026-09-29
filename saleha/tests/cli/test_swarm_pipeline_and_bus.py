"""
Unit & Integration Tests for Swarm Pipeline Engine, Event Bus, and Semantic Memory
"""

import unittest

from saleha.cli.swarm_visualizer import SwarmAsciiVisualizer
from saleha.core.memory.semantic_memory_cache import SemanticMemoryCache
from saleha.core.swarm.agent_message_bus import (
    AgentEvent,
    AgentMessageBus,
    CodeSynthesizedEvent,
    SecurityVulnerabilityEvent,
    TaskAssignedEvent,
)
from saleha.core.swarm.swarm_pipeline_engine import (
    AutonomousSwarmRouter,
    SwarmPipelineEngine,
    SwarmPipelineStage,
)
from saleha.tests.swarm_stubs import FAILING_TESTS, GOOD_CODE, stub_agents


class AgentMessageBusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = AgentMessageBus()

    def test_publish_and_subscribe(self) -> None:
        received_events = []

        def handler(event: AgentEvent) -> None:
            received_events.append(event)

        self.bus.subscribe("code_synthesized", handler)

        evt = CodeSynthesizedEvent(sender_agent="CoderAgent", source_code="def run(): pass")
        self.bus.publish(evt)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].sender_agent, "CoderAgent")
        self.assertEqual(received_events[0].source_code, "def run(): pass")

    def test_wildcard_subscription(self) -> None:
        received_all = []
        self.bus.subscribe("*", lambda e: received_all.append(e))

        self.bus.publish(TaskAssignedEvent(sender_agent="Router", task_goal="Deploy app"))
        self.bus.publish(SecurityVulnerabilityEvent(sender_agent="Security", is_secure=True))

        self.assertEqual(len(received_all), 2)
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)

    def test_unsubscribe(self) -> None:
        called = []

        def handler(e):
            called.append(1)

        self.bus.subscribe("task_assigned", handler)
        self.bus.publish(TaskAssignedEvent(task_goal="G1"))
        self.assertEqual(len(called), 1)

        self.bus.unsubscribe("task_assigned", handler)
        self.bus.publish(TaskAssignedEvent(task_goal="G2"))
        self.assertEqual(len(called), 1)


class SemanticMemoryCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = SemanticMemoryCache(storage_path=".saleha/test_mem_tmp.json")
        self.cache.clear()

    def tearDown(self) -> None:
        self.cache.clear()

    def test_store_and_search_memory(self) -> None:
        entry = self.cache.store_memory(
            category="adr",
            title="Hexagonal Architecture Pattern",
            content="Use ports and adapters to decouple core business logic from database and network layers.",
            tags=["hexagonal", "ports", "adapters"]
        )
        self.assertTrue(entry.memory_id)

        results = self.cache.search_memory("How to decouple database with ports and adapters?", top_k=1)
        self.assertTrue(len(results) >= 1)
        top_match, score = results[0]
        self.assertEqual(top_match.title, "Hexagonal Architecture Pattern")
        self.assertGreater(score, 0.1)


class SwarmPipelineRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = AutonomousSwarmRouter()

    def test_default_route(self) -> None:
        stages = self.router.route_goal_to_dag("Build simple caching service")
        self.assertIn("Architect", stages)
        self.assertIn("Coder", stages)
        self.assertIn("SecurityGuard", stages)
        self.assertIn("QALead", stages)
        self.assertIn("Reviewer", stages)
        self.assertIn("FinOpsOptimizer", stages)

    def test_frontend_ui_route(self) -> None:
        stages = self.router.route_goal_to_dag("Design modern landing page with CSS glassmorphism")
        self.assertIn("Designer", stages)
        self.assertIn("WebDev", stages)

    def test_database_and_devops_route(self) -> None:
        stages = self.router.route_goal_to_dag("PostgreSQL schema migration with Docker container deployment")
        self.assertIn("DataEngineer", stages)
        self.assertIn("DevOps", stages)

    def test_incident_route(self) -> None:
        stages = self.router.route_goal_to_dag("Production outage crash traceback incident diagnosis")
        self.assertEqual(stages[0], "SREIncident")


class SwarmPipelineEngineTests(unittest.TestCase):
    def test_end_to_end_swarm_execution(self) -> None:
        # This used to pass with no model at all: a placeholder
        # `def execute(): return True` plus `assert True` tests that were
        # never called. Now the agents are stubbed with real code and real
        # tests, and the QA stage must actually run them.
        engine = SwarmPipelineEngine()
        with stub_agents():
            res = engine.execute_swarm("Synthesize thread-safe token bucket rate limiter in Python")

        self.assertTrue(res.success, [s.output_summary for s in res.stages])
        self.assertTrue(res.code_generated)
        self.assertTrue(res.tests_ran)
        self.assertTrue(res.security_checked and res.security_clean)
        self.assertTrue(res.tests_passed)
        self.assertEqual(res.final_code, GOOD_CODE)
        qa = next(s for s in res.stages if s.agent_role == "QALead")
        self.assertEqual(qa.payload["test_count"], 1)

    def test_no_model_means_no_success(self) -> None:
        engine = SwarmPipelineEngine()
        with stub_agents(code=None):
            res = engine.execute_swarm("Synthesize token bucket")
        self.assertFalse(res.success)
        self.assertFalse(res.code_generated)
        self.assertFalse(res.tests_ran)
        self.assertEqual(res.final_code, "")
        statuses = {s.agent_role: s.status for s in res.stages}
        self.assertEqual(statuses["Coder"], "failed")
        self.assertEqual(statuses["QALead"], "skipped")
        self.assertEqual(statuses["SecurityGuard"], "skipped")

    def test_failing_tests_fail_the_run(self) -> None:
        engine = SwarmPipelineEngine()
        with stub_agents(tests=FAILING_TESTS):
            res = engine.execute_swarm("Synthesize token bucket")
        self.assertTrue(res.tests_ran)
        self.assertFalse(res.tests_passed)
        self.assertFalse(res.success)

    def test_no_tests_generated_is_not_a_pass(self) -> None:
        engine = SwarmPipelineEngine()
        with stub_agents(tests=None):
            res = engine.execute_swarm("Synthesize token bucket")
        self.assertFalse(res.tests_ran)
        self.assertFalse(res.success)

    def test_unimplemented_roles_are_skipped_not_success(self) -> None:
        engine = SwarmPipelineEngine()
        with stub_agents():
            res = engine.execute_swarm("Deploy with docker the token bucket")
        devops = next(s for s in res.stages if s.agent_role == "DevOps")
        self.assertEqual(devops.status, "skipped")


class SwarmVisualizerTests(unittest.TestCase):
    def test_visualizer_renders_without_error(self) -> None:
        vis = SwarmAsciiVisualizer()
        stage = SwarmPipelineStage(stage_id="s1", agent_role="Architect", status="success", duration_ms=12.4, output_summary="ADR generated")
        vis.render_header("Test Goal")
        vis.render_stage_update(stage, 1, 3)


if __name__ == "__main__":
    unittest.main()
