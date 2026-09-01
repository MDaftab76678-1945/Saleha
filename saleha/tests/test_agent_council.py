"""Unit tests for Multi-Agent Architectural Council & Debate Engine."""

from __future__ import annotations

import unittest
from saleha.core.agent_council import AgentCouncil, CouncilProposal, CouncilDebateResult


class AgentCouncilTests(unittest.TestCase):

    def setUp(self):
        self.council = AgentCouncil()

    def test_proposal_overall_score_calculation(self):
        proposal = CouncilProposal(
            persona_name="Test Persona",
            perspective="Test Perspective",
            proposed_code="def test(): pass",
            key_arguments=["arg1", "arg2"],
            security_score=100,
            performance_score=90,
            maintainability_score=80,
            simplicity_score=70,
        )
        # (100 * 0.3) + (90 * 0.3) + (80 * 0.25) + (70 * 0.15) = 30 + 27 + 20 + 10.5 = 87.5
        self.assertEqual(proposal.overall_score, 87.5)

    def test_generate_proposals_returns_three_personas(self):
        proposals = self.council.generate_proposals("Distributed Rate Limiter")
        self.assertEqual(len(proposals), 3)

        personas = [p.persona_name for p in proposals]
        self.assertTrue(any("Security" in p for p in personas))
        self.assertTrue(any("Performance" in p for p in personas))
        self.assertTrue(any("Architect" in p for p in personas))

    def test_debate_and_synthesize_consensus(self):
        res: CouncilDebateResult = self.council.debate_and_synthesize("Design Cache Layer")
        self.assertEqual(res.problem_statement, "Design Cache Layer")
        self.assertIn("HighThroughputService", res.consensus_code)
        self.assertIn("Trade-Off Analysis", res.trade_off_analysis)
        self.assertIn("Cross-Agent Adversarial Critiques Addressed", res.trade_off_analysis)
        self.assertGreater(res.total_consensus_score, 80.0)
        self.assertGreaterEqual(res.duration_sec, 0.0)

    def test_critique_proposals_generates_cross_critiques(self):
        proposals = self.council.generate_proposals("Rate Limiter")
        critiques = self.council.critique_proposals(proposals)
        self.assertEqual(len(critiques), 3)
        for persona, c_list in critiques.items():
            self.assertGreaterEqual(len(c_list), 1)


if __name__ == "__main__":
    unittest.main()
