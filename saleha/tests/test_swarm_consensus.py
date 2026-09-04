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

    def test_unauthorized_voter_rejected(self):
        prop = self.consensus.propose("AgentA", "mod.py", "pass")
        with self.assertRaises(PermissionError):
            self.consensus.cast_prepare_vote(prop.proposal_id, "RogueHackerAgent", True)

    def test_duplicate_vote_not_counted_twice(self):
        prop = self.consensus.propose("AgentA", "mod.py", "pass")
        # AgentA votes 5 times
        for _ in range(5):
            self.consensus.cast_prepare_vote(prop.proposal_id, "AgentA", True)
            self.consensus.cast_commit_vote(prop.proposal_id, "AgentA", True)

        dec = self.consensus.evaluate_consensus(prop.proposal_id)
        self.assertEqual(dec.prepare_votes, 1)
        self.assertFalse(dec.committed)

    def test_confidence_weighted_consensus_high_confidence(self):
        weighted_consensus = SwarmPBFTConsensus(
            ["ArchitectAgent", "SecurityAgent", "TesterAgent", "CoderAgent"],
            weights={"ArchitectAgent": 2.0, "SecurityAgent": 2.5, "TesterAgent": 1.5, "CoderAgent": 1.0}
        )
        prop = weighted_consensus.propose("CoderAgent", "core.py", "def execute(): return True")
        # High-weight agents approve with high confidence
        weighted_consensus.cast_prepare_vote(prop.proposal_id, "ArchitectAgent", True, confidence=0.95)
        weighted_consensus.cast_prepare_vote(prop.proposal_id, "SecurityAgent", True, confidence=0.9)
        weighted_consensus.cast_commit_vote(prop.proposal_id, "ArchitectAgent", True, confidence=0.95)
        weighted_consensus.cast_commit_vote(prop.proposal_id, "SecurityAgent", True, confidence=0.9)

        dec = weighted_consensus.evaluate_confidence_weighted_consensus(prop.proposal_id, threshold=0.5)
        self.assertTrue(dec.committed)
        self.assertIn("CP-WBFT Weighted Consensus", dec.summary)

    def test_confidence_weighted_consensus_low_confidence_rejected(self):
        weighted_consensus = SwarmPBFTConsensus(
            ["ArchitectAgent", "SecurityAgent", "TesterAgent", "CoderAgent"],
            weights={"ArchitectAgent": 1.0, "SecurityAgent": 1.0, "TesterAgent": 1.0, "CoderAgent": 1.0}
        )
        prop = weighted_consensus.propose("CoderAgent", "risky.py", "eval(user_input)")
        # Agents vote with low confidence
        weighted_consensus.cast_prepare_vote(prop.proposal_id, "ArchitectAgent", True, confidence=0.2)
        weighted_consensus.cast_commit_vote(prop.proposal_id, "ArchitectAgent", True, confidence=0.2)

        dec = weighted_consensus.evaluate_confidence_weighted_consensus(prop.proposal_id, threshold=0.66)
        self.assertFalse(dec.committed)


if __name__ == "__main__":
    unittest.main()
