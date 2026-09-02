"""
Unit & Integration Tests for Swarm Pipeline Engine, Event Bus, and Semantic Memory
"""

import unittest
from saleha.core.agent_message_bus import (
    AgentMessageBus,
    AgentEvent,
    TaskAssignedEvent,
    CodeSynthesizedEvent,
    SecurityVulnerabilityEvent,
    TestExecutionEvent,
)
from saleha.core.semantic_memory_cache import SemanticMemoryCache
from saleha.core.swarm_pipeline_engine import (
    AutonomousSwarmRouter,
    SwarmPipelineEngine,
    SwarmPipelineStage,
)
from saleha.cli.swarm_visualizer import SwarmAsciiVisualizer


class AgentMessageBusTests(unittest.TestCase):
    def setUp(self):
        self.bus = AgentMessageBus()

    def test_publish_and_subscribe(self):
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        self.bus.subscribe("code_synthesized", handler)

        evt = CodeSynthesizedEvent(sender_agent="CoderAgent", source_code="def run(): pass")
        self.bus.publish(evt)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].sender_agent, "CoderAgent")
        self.assertEqual(received_events[0].source_code, "def run(): pass")

    def test_wildcard_subscription(self):
        received_all = []
        self.bus.subscribe("*", lambda e: received_all.append(e))

        self.bus.publish(TaskAssignedEvent(sender_agent="Router", task_goal="Deploy app"))
        self.bus.publish(SecurityVulnerabilityEvent(sender_agent="Security", is_secure=True))

        self.assertEqual(len(received_all), 2)
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)

    def test_unsubscribe(self):
        called = []
        handler = lambda e: called.append(1)
        self.bus.subscribe("task_assigned", handler)
        self.bus.publish(TaskAssignedEvent(task_goal="G1"))
        self.assertEqual(len(called), 1)

        self.bus.unsubscribe("task_assigned", handler)
        self.bus.publish(TaskAssignedEvent(task_goal="G2"))
        self.assertEqual(len(called), 1)


class SemanticMemoryCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = SemanticMemoryCache(storage_path=".saleha/test_mem_tmp.json")
        self.cache.clear()

    def tearDown(self):
        self.cache.clear()

    def test_store_and_search_memory(self):
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
    def setUp(self):
        self.router = AutonomousSwarmRouter()

    def test_default_route(self):
        stages = self.router.route_goal_to_dag("Build simple caching service")
        self.assertIn("Architect", stages)
        self.assertIn("Coder", stages)
        self.assertIn("SecurityGuard", stages)
        self.assertIn("QALead", stages)
        self.assertIn("Reviewer", stages)
        self.assertIn("FinOpsOptimizer", stages)

    def test_frontend_ui_route(self):
        stages = self.router.route_goal_to_dag("Design modern landing page with CSS glassmorphism")
        self.assertIn("Designer", stages)
        self.assertIn("WebDev", stages)

    def test_database_and_devops_route(self):
        stages = self.router.route_goal_to_dag("PostgreSQL schema migration with Docker container deployment")
        self.assertIn("DataEngineer", stages)
        self.assertIn("DevOps", stages)

    def test_incident_route(self):
        stages = self.router.route_goal_to_dag("Production outage crash traceback incident diagnosis")
        self.assertEqual(stages[0], "SREIncident")


class SwarmPipelineEngineTests(unittest.TestCase):
    def test_end_to_end_swarm_execution(self):
        engine = SwarmPipelineEngine()
        res = engine.execute_swarm("Synthesize thread-safe token bucket rate limiter in Python")

        self.assertTrue(res.success)
        self.assertTrue(res.execution_id)
        self.assertIn("ADR", res.adr_title)
        self.assertTrue(res.security_clean)
        self.assertTrue(res.tests_passed)
        self.assertTrue(res.final_code)
        self.assertTrue(len(res.stages) >= 6)


class SwarmVisualizerTests(unittest.TestCase):
    def test_visualizer_renders_without_error(self):
        vis = SwarmAsciiVisualizer()
        stage = SwarmPipelineStage(stage_id="s1", agent_role="Architect", status="success", duration_ms=12.4, output_summary="ADR generated")
        vis.render_header("Test Goal")
        vis.render_stage_update(stage, 1, 3)


if __name__ == "__main__":
    unittest.main()
