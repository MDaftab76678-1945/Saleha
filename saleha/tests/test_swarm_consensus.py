"""Unit tests for Swarm PBFT Consensus Protocol."""

import unittest
from saleha.core.swarm_consensus import SwarmPBFTConsensus, SwarmProposal, ConsensusDecision


class TestSwarmConsensus(unittest.TestCase):
    """Test suite for SwarmPBFTConsensus Byzantine Fault Tolerance and quorum voting."""

    def setUp(self):
        self.consensus = SwarmPBFTConsensus(["AgentA", "AgentB", "AgentC", "AgentD"])

    def test_propose_creates_proposal(self):
        prop = self.consensus.propose("AgentA", "auth.py", "def login(): pass")
        self.assertIsInstance(prop, SwarmProposal)
        self.assertEqual(prop.proposer_agent_id, "AgentA")

    def test_quorum_consensus_achieved(self):
        prop = self.consensus.propose("AgentA", "auth.py", "def login(): pass")
        for v in ["AgentA", "AgentB", "AgentC"]:
            self.consensus.cast_prepare_vote(prop.proposal_id, v, True)
            self.consensus.cast_commit_vote(prop.proposal_id, v, True)

        dec = self.consensus.evaluate_consensus(prop.proposal_id)
        self.assertIsInstance(dec, ConsensusDecision)
        self.assertTrue(dec.committed)
        self.assertEqual(dec.prepare_votes, 3)

    def test_rejection_when_votes_insufficient(self):
        prop = self.consensus.propose("AgentA", "bad.py", "malicious_code()")
        self.consensus.cast_prepare_vote(prop.proposal_id, "AgentA", True)
        self.consensus.cast_prepare_vote(prop.proposal_id, "AgentB", False)

        dec = self.consensus.evaluate_consensus(prop.proposal_id)
        self.assertFalse(dec.committed)


if __name__ == "__main__":
    unittest.main()
