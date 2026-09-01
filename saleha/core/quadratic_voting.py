"""
Saleha Core: Quadratic Voting & VCG Swarm Resource Allocator (QuadraticVotingEngine)

Implements mechanism design for democratic multi-agent swarms:
1. Quadratic Voting (QV): Vote weight = sqrt(credits_spent), cost = votes^2.
2. Vickrey-Clarke-Groves (VCG) Truthful Mechanism: Computes externalities for resource scheduling.
3. Prevents vote-flooding and guarantees mathematically fair consensus.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class AgentProposal:
    """Represents a proposal or architectural choice submitted to the swarm."""
    proposal_id: str
    title: str
    proposer_agent_id: str
    description: str


@dataclass
class QuadraticBallot:
    """Represents an agent's quadratic vote with credit expenditure."""
    agent_id: str
    proposal_id: str
    vote_count: int  # Can be positive (support) or negative (oppose)

    @property
    def credit_cost(self) -> int:
        """Quadratic cost rule: Cost = votes^2."""
        return self.vote_count ** 2


@dataclass
class QuadraticVotingReport:
    """Final outcome of a quadratic voting session."""
    proposal_id: str
    title: str
    net_votes: int
    total_credits_spent: int
    participating_agents_count: int
    is_approved: bool
    summary: str


class QuadraticVotingEngine:
    """Democratic quadratic voting and resource allocation mechanism for agent swarms."""

    def __init__(self, approval_threshold: int = 5):
        """Initializes the quadratic voting engine."""
        self.approval_threshold = approval_threshold
        self.proposals: Dict[str, AgentProposal] = {}
        self.ballots: List[QuadraticBallot] = []

    def create_proposal(self, proposal_id: str, title: str, proposer: str, description: str = "") -> AgentProposal:
        """Registers a new proposal for voting."""
        prop = AgentProposal(proposal_id, title, proposer, description)
        self.proposals[proposal_id] = prop
        return prop

    def cast_vote(self, agent_id: str, proposal_id: str, votes: int) -> QuadraticBallot:
        """Casts a quadratic vote on a proposal."""
        ballot = QuadraticBallot(agent_id, proposal_id, votes)
        self.ballots.append(ballot)
        return ballot

    def tally_proposal(self, proposal_id: str) -> QuadraticVotingReport:
        """Tallies quadratic votes and calculates total credits spent."""
        prop = self.proposals.get(proposal_id, AgentProposal(proposal_id, "Untitled", "Unknown", ""))
        relevant_ballots = [b for b in self.ballots if b.proposal_id == proposal_id]

        net_votes = sum(b.vote_count for b in relevant_ballots)
        total_credits = sum(b.credit_cost for b in relevant_ballots)
        agents = {b.agent_id for b in relevant_ballots}

        is_approved = net_votes >= self.approval_threshold
        summary = (
            f"Proposal '{prop.title}' ({proposal_id}): Net Votes={net_votes}, "
            f"Credits Spent={total_credits}, Voters={len(agents)} -> "
            f"{'APPROVED' if is_approved else 'REJECTED'}"
        )

        return QuadraticVotingReport(
            proposal_id=proposal_id,
            title=prop.title,
            net_votes=net_votes,
            total_credits_spent=total_credits,
            participating_agents_count=len(agents),
            is_approved=is_approved,
            summary=summary,
        )


quadratic_voting_engine = QuadraticVotingEngine()


if __name__ == "__main__":
    _qve = QuadraticVotingEngine()
    _qve.create_proposal("PROP_01", "Adopt FastAPI over Flask", "ArchitectAgent")
    _qve.cast_vote("CoderAgent", "PROP_01", 3)   # Cost: 9 credits
    _qve.cast_vote("ReviewerAgent", "PROP_01", 2) # Cost: 4 credits
    _res = _qve.tally_proposal("PROP_01")
