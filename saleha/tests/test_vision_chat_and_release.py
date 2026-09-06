"""
Unit & Integration Tests for Vision Designer, Swarm Chat Session, and Release Manager
"""

import unittest
from saleha.agents.vision_designer import VisionDesignerAgent, VisionLayoutSpec, vision_designer
from saleha.cli.chat_session import SwarmChatSession
from saleha.tools.release_manager import SalehaReleaseManager, ReleaseCheckReport
from rich.console import Console
import io


class VisionDesignerAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = VisionDesignerAgent()

    def test_synthesize_from_wireframe_dashboard(self):
        spec: VisionLayoutSpec = self.agent.synthesize_from_wireframe("Analytics Dashboard with Metrics Cards and Dark Theme")
        self.assertEqual(spec.layout_type, "Dashboard Grid")
        self.assertTrue(len(spec.color_palette) >= 4)
        self.assertIn("var(--bg-base)", spec.css_styles)
        self.assertIn("import React from \"react\"", spec.jsx_component)
        self.assertIn("<!DOCTYPE html>", spec.html_markup)
        self.assertGreaterEqual(spec.generation_time_ms, 0.0)

    def test_execute_agent_response(self):
        resp = self.agent.execute("SaaS Landing Hero with CTA buttons")
        self.assertTrue(resp.success)
        self.assertIn("Synthesized", resp.content)


class SwarmChatSessionTests(unittest.TestCase):
    def setUp(self):
        self.string_io = io.StringIO()
        self.console = Console(file=self.string_io, force_terminal=False)
        self.session = SwarmChatSession(console=self.console)

    def test_process_slash_commands(self):
        # /agents
        self.assertTrue(self.session.process_command("/agents"))
        output = self.string_io.getvalue()
        self.assertIn("ArchitectAgent", output)
        self.assertIn("CoderAgent", output)

        # /clear
        self.assertTrue(self.session.process_command("/clear"))

        # /exit
        self.assertFalse(self.session.process_command("/exit"))

    def test_process_chat_turn(self):
        self.assertTrue(self.session.process_command("How do I implement binary search in Python?"))
        self.assertEqual(len(self.session.history), 2)
        self.assertEqual(self.session.history[0]["role"], "user")
        self.assertEqual(self.session.history[1]["role"], "assistant")


class SalehaReleaseManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = SalehaReleaseManager()

    def test_check_release_readiness(self):
        report: ReleaseCheckReport = self.manager.check_release_readiness()
        self.assertTrue(report.pyproject_valid)
        self.assertTrue(report.cargo_valid)
        self.assertTrue(report.packages_valid)
        self.assertEqual(report.checks_passed, report.total_checks)
        self.assertTrue(report.success)
        self.assertEqual(len(report.issues), 0)


if __name__ == "__main__":
    unittest.main()
