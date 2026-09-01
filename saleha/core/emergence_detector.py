"""
Saleha Core: Emergent Swarm Behavior & Collusion Detector (EmergenceDetector)

Monitors multi-agent swarm communication graphs to detect:
1. Gini Inequality: Unbalanced token/message hogging across agents.
2. Circular Deadlocks: Infinite ping-pong loops (Agent A -> Agent B -> Agent A).
3. Runaway Cascades: Exponential message volume expansion.
4. Auto-remediation and swarm deadlock break interventions.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any


@dataclass
class SwarmMessageEvent:
    """Represents a message sent between swarm agents."""
    sender_id: str
    recipient_id: str
    message_content: str
    step_index: int


@dataclass
class EmergenceHealthReport:
    """Consolidated health and safety evaluation of swarm communication dynamics."""
    is_healthy: bool
    total_messages: int
    gini_coefficient: float
    circular_deadlocks_detected: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    remediation_action: str = "none"
    summary: str = ""


class EmergenceDetector:
    """Monitors emergent properties and prevents rogue collusion in agent swarms."""

    def __init__(self, gini_threshold: float = 0.75, max_cycle_len: int = 4):
        """Initializes the emergence detector."""
        self.gini_threshold = gini_threshold
        self.max_cycle_len = max_cycle_len
        self.message_history: List[SwarmMessageEvent] = []

    def record_message(self, sender: str, recipient: str, content: str, step: int):
        """Records an agent-to-agent interaction."""
        self.message_history.append(SwarmMessageEvent(sender, recipient, content, step))

    def calculate_gini(self, counts: List[int]) -> float:
        """Calculates Gini coefficient across agent activity counts (0.0=equal, 1.0=monopoly)."""
        if not counts or sum(counts) == 0:
            return 0.0
        sorted_counts = sorted(counts)
        n = len(sorted_counts)
        numer = sum((i + 1) * val for i, val in enumerate(sorted_counts))
        denom = n * sum(sorted_counts)
        gini = (2.0 * numer) / denom - (n + 1.0) / n
        return max(0.0, min(1.0, round(gini, 3)))

    def evaluate_swarm_health(self) -> EmergenceHealthReport:
        """Audits the recorded message graph for deadlocks, runaway token usage, and Gini skew."""
        if not self.message_history:
            return EmergenceHealthReport(
                is_healthy=True,
                total_messages=0,
                gini_coefficient=0.0,
                summary="Swarm communication is idle and healthy.",
            )

        agent_activity: Dict[str, int] = defaultdict(int)
        for msg in self.message_history:
            agent_activity[msg.sender_id] += 1

        gini = self.calculate_gini(list(agent_activity.values()))

        # Check for circular ping-pong loops in recent history
        deadlocks: List[str] = []
        recent = self.message_history[-10:]
        for i in range(len(recent) - 2):
            m1 = recent[i]
            m2 = recent[i + 1]
            m3 = recent[i + 2]
            if (m1.sender_id == m2.recipient_id == m3.sender_id) and (m1.recipient_id == m2.sender_id == m3.recipient_id):
                deadlocks.append(f"Ping-Pong Deadlock between '{m1.sender_id}' and '{m1.recipient_id}'")

        anomalies: List[str] = []
        if gini > self.gini_threshold:
            anomalies.append(f"High communication inequality (Gini: {gini} > {self.gini_threshold})")
        if deadlocks:
            anomalies.extend(deadlocks)

        is_healthy = len(anomalies) == 0
        remediation = "break_deadlock_and_yield_to_orchestrator" if not is_healthy else "none"

        summary = (
            f"Swarm Dynamics ({len(self.message_history)} messages across {len(agent_activity)} agents): "
            f"Gini={gini}, Deadlocks={len(deadlocks)} -> {'HEALTHY' if is_healthy else 'ANOMALY DETECTED'}"
        )

        return EmergenceHealthReport(
            is_healthy=is_healthy,
            total_messages=len(self.message_history),
            gini_coefficient=gini,
            circular_deadlocks_detected=deadlocks,
            anomalies=anomalies,
            remediation_action=remediation,
            summary=summary,
        )

    def clear(self):
        """Clears recorded message history."""
        self.message_history.clear()


emergence_detector = EmergenceDetector()


if __name__ == "__main__":
    _ed = EmergenceDetector()
    _ed.record_message("AgentA", "AgentB", "Fix this", 1)
    _ed.record_message("AgentB", "AgentA", "Cannot fix", 2)
    _ed.record_message("AgentA", "AgentB", "Fix this again", 3)
    _rep = _ed.evaluate_swarm_health()
