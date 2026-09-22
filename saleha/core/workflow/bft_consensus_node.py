"""
Saleha Workflow Engine: Byzantine Fault Tolerant (BFT) Consensus Node.

Coordinates multi-agent or multi-model voting on high-stakes workflow decisions,
eliminating single-model hallucinations and output corruptions.
"""

from __future__ import annotations

import collections
from typing import Any, Callable, Dict, List, Optional

from saleha.core.workflow.nodes import NodeStatus, WorkflowExecutionContext, WorkflowNode


class BFTConsensusNode(WorkflowNode):
    """
    Byzantine Fault Tolerant voting node.
    Requires a quorum of independent voters before ratifying an outcome.
    """

    def __init__(
        self,
        node_id: str,
        title: str,
        voters: List[Callable[[Dict[str, Any], WorkflowExecutionContext], str]],
        quorum_fraction: float = 0.66,
        depends_on: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type="bft_consensus", depends_on=depends_on, config=config)
        self.voters = voters
        self.quorum_fraction = quorum_fraction

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        inputs = self.resolve_inputs(context)
        votes: List[str] = []
        voter_details: Dict[str, str] = {}

        for idx, voter_fn in enumerate(self.voters):
            voter_name = getattr(voter_fn, "__name__", f"voter_{idx + 1}")
            try:
                vote = voter_fn(inputs, context).strip()
                votes.append(vote)
                voter_details[voter_name] = vote
            except Exception as e:
                voter_details[voter_name] = f"ERROR: {str(e)}"
                context.log(f"BFT: Voter '{voter_name}' failed: {e}")

        if not votes:
            raise RuntimeError(f"BFT Consensus Node '{self.id}' failed: All voters crashed.")

        # Count frequencies
        counter = collections.Counter(votes)
        winner, count = counter.most_common(1)[0]
        consensus_ratio = count / len(self.voters)
        is_quorum_reached = consensus_ratio >= self.quorum_fraction

        if not is_quorum_reached:
            raise RuntimeError(
                f"BFT Consensus Node '{self.id}' failed to reach quorum: "
                f"Highest vote '{winner}' achieved {consensus_ratio:.2%} (Threshold: {self.quorum_fraction:.2%})"
            )

        context.log(
            f"BFT Consensus [RATIFIED]: Outcome '{winner}' achieved "
            f"{count}/{len(self.voters)} votes ({consensus_ratio:.2%})"
        )

        out = {
            "decision": winner,
            "confidence": round(consensus_ratio, 3),
            "vote_count": count,
            "total_voters": len(self.voters),
            "voter_details": voter_details,
        }
        self.status = NodeStatus.COMPLETED
        self.outputs = out
        return out
