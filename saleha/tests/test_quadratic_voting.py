"""Unit tests for Quadratic Voting & VCG Swarm Allocator."""

import unittest
from saleha.core.quadratic_voting import QuadraticVotingEngine, QuadraticVotingReport


class TestQuadraticVoting(unittest.TestCase):
    """Test suite for QuadraticVotingEngine democratic consensus and cost formula."""

    def setUp(self):
        self.engine = QuadraticVotingEngine(approval_threshold=4)

    def test_quadratic_credit_cost_calculation(self):
        self.engine.create_proposal("P1", "Migrate to SQLite", "DatabaseAgent")
        b1 = self.engine.cast_vote("AgentA", "P1", 3)
        self.assertEqual(b1.credit_cost, 9)  # 3^2 = 9

        b2 = self.engine.cast_vote("AgentB", "P1", 2)
        self.assertEqual(b2.credit_cost, 4)  # 2^2 = 4

        rep = self.engine.tally_proposal("P1")
        self.assertIsInstance(rep, QuadraticVotingReport)
        self.assertEqual(rep.net_votes, 5)
        self.assertEqual(rep.total_credits_spent, 13)
        self.assertTrue(rep.is_approved)


if __name__ == "__main__":
    unittest.main()
