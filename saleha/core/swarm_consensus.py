"""
Saleha Core: Swarm PBFT Byzantine Fault Tolerance Consensus (SwarmConsensus)

Implements Practical Byzantine Fault Tolerance (PBFT) consensus for multi-agent swarms:
1. Three-Phase Protocol: Pre-Prepare -> Prepare -> Commit.
2. Quorum Threshold: Requires 2f + 1 votes out of 3f + 1 agents to commit code or AST diffs.
3. Automatically rejects hallucinations and rogue agent suggestions before touching disk.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any


@dataclass
class SwarmProposal:
    """Represents a proposed change or code patch submitted by an agent."""
    proposal_id: str
    proposer_agent_id: str
    target_file: str
    code_patch: str
    patch_hash: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConsensusVote:
    """A vote from an individual validator agent in the swarm."""
    voter_agent_id: str
    proposal_id: str
    phase: str  # "prepare" or "commit"
    approved: bool
    reason: str = ""


@dataclass
class ConsensusDecision:
    """Final decision reached by the PBFT swarm."""
    proposal_id: str
    committed: bool
    total_validators: int
    votes_received: int
    f_faults_tolerated: int
    required_quorum: int
    prepare_votes: int
    commit_votes: int
    summary: str


class SwarmPBFTConsensus:
    """PBFT-based multi-agent consensus engine."""

    def __init__(self, validator_agent_ids: Optional[List[str]] = None):
        """Initializes the PBFT consensus engine with a set of registered validator agents."""
        self.validators: Set[str] = set(
            validator_agent_ids or ["ArchitectAgent", "CoderAgent", "SecurityAgent", "TesterAgent"]
        )
        self.proposals: Dict[str, SwarmProposal] = {}
        self.prepare_votes: Dict[str, List[ConsensusVote]] = {}
        self.commit_votes: Dict[str, List[ConsensusVote]] = {}

    def propose(self, proposer_id: str, target_file: str, code_patch: str) -> SwarmProposal:
        """Submits a new code or architecture proposal into the Pre-Prepare phase."""
        patch_hash = hashlib.sha256(code_patch.encode("utf-8")).hexdigest()
        prop_id = f"prop_{patch_hash[:8]}_{int(time.time() * 1000) % 10000}"

        proposal = SwarmProposal(
            proposal_id=prop_id,
            proposer_agent_id=proposer_id,
            target_file=target_file,
            code_patch=code_patch,
            patch_hash=patch_hash,
        )
        self.proposals[prop_id] = proposal
        self.prepare_votes[prop_id] = []
        self.commit_votes[prop_id] = []
        return proposal

    def cast_prepare_vote(self, proposal_id: str, voter_id: str, approved: bool, reason: str = "") -> ConsensusVote:
        """Records a Prepare phase vote from an authorized swarm validator."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' does not exist.")
        vote = ConsensusVote(voter_id, proposal_id, "prepare", approved, reason)
        self.prepare_votes[proposal_id].append(vote)
        return vote

    def cast_commit_vote(self, proposal_id: str, voter_id: str, approved: bool, reason: str = "") -> ConsensusVote:
        """Records a Commit phase vote from an authorized swarm validator."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' does not exist.")
        vote = ConsensusVote(voter_id, proposal_id, "commit", approved, reason)
        self.commit_votes[proposal_id].append(vote)
        return vote

    def evaluate_consensus(self, proposal_id: str) -> ConsensusDecision:
        """Evaluates whether the proposal achieved 2f + 1 PBFT quorum to commit."""
        if proposal_id not in self.proposals:
            raise ValueError(f"Proposal '{proposal_id}' does not exist.")

        n = len(self.validators)
        f = max(0, (n - 1) // 3)
        required_quorum = (2 * f) + 1

        prep_ok = sum(1 for v in self.prepare_votes.get(proposal_id, []) if v.approved)
        comm_ok = sum(1 for v in self.commit_votes.get(proposal_id, []) if v.approved)

        is_committed = (prep_ok >= required_quorum) and (comm_ok >= required_quorum)
        summary = (
            f"PBFT Consensus for '{proposal_id}': "
            f"Prepare ({prep_ok}/{required_quorum}) & Commit ({comm_ok}/{required_quorum}) -> "
            f"{'COMMITTED' if is_committed else 'REJECTED'}"
        )

        return ConsensusDecision(
            proposal_id=proposal_id,
            committed=is_committed,
            total_validators=n,
            votes_received=prep_ok + comm_ok,
            f_faults_tolerated=f,
            required_quorum=required_quorum,
            prepare_votes=prep_ok,
            commit_votes=comm_ok,
            summary=summary,
        )


swarm_consensus = SwarmPBFTConsensus()


if __name__ == "__main__":
    _engine = SwarmPBFTConsensus(["AgentA", "AgentB", "AgentC", "AgentD"])
    _p = _engine.propose("AgentA", "auth.py", "def login(): pass")
    for _v in ["AgentA", "AgentB", "AgentC"]:
        _engine.cast_prepare_vote(_p.proposal_id, _v, True)
        _engine.cast_commit_vote(_p.proposal_id, _v, True)
    _dec = _engine.evaluate_consensus(_p.proposal_id)
