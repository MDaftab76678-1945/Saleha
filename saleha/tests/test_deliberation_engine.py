import unittest
import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from saleha.core.deliberation_engine import DeliberationEngine, DeliberationResult
from saleha.core.team_orchestrator import TeamResult
from saleha.cli.commands import cli


class DeliberationEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = DeliberationEngine(model="test-model")

    def test_deliberate_and_build_mock(self):
        with patch.object(self.engine, "_get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.think.side_effect = [
                MagicMock(success=True, content="1. Initial LLD"),
                MagicMock(success=True, content="2. Security Critique: Add rate limiting"),
                MagicMock(success=True, content="3. SDE Critique: Use O(1) hash map"),
                MagicMock(success=True, content="4. Consensus Architecture Specification"),
                MagicMock(success=True, content="```python\nimport unittest\nclass Test(unittest.TestCase):\n    def test_run(self): pass\n```"),
                MagicMock(success=True, content="```python\ndef solve(): return True\n```"),
            ]
            mock_get_agent.return_value = mock_agent

            result: DeliberationResult = self.engine.deliberate_and_build("Design a rate limiter")
            self.assertTrue(result.success)
            self.assertEqual(result.initial_design, "1. Initial LLD")
            self.assertIn("Security Critique", result.security_critique)
            self.assertIn("SDE Critique", result.sde_critique)
            self.assertEqual(result.consensus_design, "4. Consensus Architecture Specification")
            self.assertIn("def solve():", result.final_code)

    def test_cli_team_with_debate_flag(self):
        fake_team_result = TeamResult(
            success=True,
            goal="Build secure cache",
            prd="PRD",
            design="Consensus Design",
            code="class Cache: pass",
            security_report="APPROVED",
            test_code="class Test: pass",
            stages_completed=["Product Management", "Architecture & Consensus Deliberation", "Implementation", "Security Audit", "Test Automation"],
            attempts=1,
            log="Debate swarm completed"
        )
        with patch("saleha.cli.commands.TeamOrchestrator") as orchestrator_class:
            orchestrator_class.return_value.run_team_workflow.return_value = fake_team_result
            result = CliRunner().invoke(cli, ["team", "Build secure cache", "--debate", "--json"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertTrue(payload["success"])
        self.assertIn("Architecture & Consensus Deliberation", payload["stages_completed"])


if __name__ == "__main__":
    unittest.main()

