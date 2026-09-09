"""Unit tests for Quadratic Voting & VCG Swarm Allocator."""

import unittest
from click.testing import CliRunner
from saleha.core.quadratic_voting import QuadraticVotingEngine, QuadraticVotingReport
from saleha.cli.commands import cli


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


class QuadraticVoteCLITests(unittest.TestCase):
    """Tests for the `quadratic-vote` CLI command.

    This used to replay one fixed hardcoded scenario every run -- same
    proposal, same two votes -- regardless of input, because it took no
    arguments at all. It now takes a real title and real --vote agent:count
    options; these tests exist to prove two different invocations actually
    produce different results.
    """

    def setUp(self):
        self.runner = CliRunner()

    def test_different_inputs_produce_different_output(self):
        r1 = self.runner.invoke(cli, ['quadratic-vote', 'Migrate to PostgreSQL',
                                      '--vote', 'DataAgent:4', '--vote', 'CoderAgent:2'])
        r2 = self.runner.invoke(cli, ['quadratic-vote', 'Rewrite in Rust',
                                      '--vote', 'PerfAgent:5'])
        self.assertEqual(r1.exit_code, 0)
        self.assertEqual(r2.exit_code, 0)
        self.assertIn('Migrate to PostgreSQL', r1.output)
        self.assertIn('Net Votes=6', r1.output)  # 4 + 2
        self.assertIn('Rewrite in Rust', r2.output)
        self.assertIn('Net Votes=5', r2.output)
        self.assertNotEqual(r1.output, r2.output)

    def test_negative_vote_counts_as_opposition(self):
        result = self.runner.invoke(cli, ['quadratic-vote', 'Controversial change',
                                          '--vote', 'AgentA:3', '--vote', 'AgentB:-2'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Net Votes=1', result.output)  # 3 + (-2)
        self.assertIn('REJECTED', result.output)  # below default threshold of 5

    def test_malformed_vote_is_rejected_not_silently_skipped(self):
        result = self.runner.invoke(cli, ['quadratic-vote', 'Test', '--vote', 'not-a-valid-format'])
        self.assertNotEqual(result.exit_code, 0)

    def test_non_integer_vote_count_is_rejected(self):
        result = self.runner.invoke(cli, ['quadratic-vote', 'Test', '--vote', 'Agent:notanumber'])
        self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
