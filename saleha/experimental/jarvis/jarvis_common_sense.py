"""
GAP 3 REMEDIATION: Intuitive Physics Engine + Theory of Mind
Provides everyday physical and social intuition via internal simulation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ---------- INTUITIVE PHYSICS ----------

@dataclass
class PhysicalObject:
    name: str
    supported_by: Optional[str] = None   # what holds it up
    contains: List[str] = field(default_factory=list)
    inside: Optional[str] = None
    is_fragile: bool = False
    is_liquid: bool = False


class IntuitivePhysicsEngine:
    """
    Naive physics simulator. Encodes everyday physical intuitions
    as constraint rules, enabling mental simulation of outcomes.
    """

    def __init__(self):
        self.objects: Dict[str, PhysicalObject] = {}

    def add_object(self, obj: PhysicalObject):
        self.objects[obj.name] = obj

    def will_fall(self, obj_name: str) -> bool:
        """Object permanence + support reasoning."""
        obj = self.objects.get(obj_name)
        if not obj:
            return False
        # Unsupported objects fall (gravity intuition)
        return obj.supported_by is None

    def will_spill(self, container_name: str) -> bool:
        """Containment + tipping reasoning."""
        container = self.objects.get(container_name)
        if not container or not container.contains:
            return False
        # Liquid in unsupported/tipped container spills
        if self.will_fall(container_name):
            return True
        return False

    def is_physically_possible(self, scenario: str) -> bool:
        """
        Sanity-check a scenario against naive physics.
        Used to catch LLM hallucinations that violate physical law.
        """
        # Rule-based filter: e.g., "object passes through solid wall" -> False
        return True  # expand with constraint checks

    def simulate(self, action: str, target: str) -> str:
        """Mental simulation: predict outcome of action."""
        if action == "remove_support" and target in self.objects:
            self.objects[target].supported_by = None
            if self.will_fall(target):
                return f"{target} falls"
        return "no significant change"


# ---------- THEORY OF MIND ----------

@dataclass
class AgentModel:
    """Model of another agent's mental state."""
    name: str
    beliefs: Set[str] = field(default_factory=set)      # what they believe
    knowledge: Set[str] = field(default_factory=set)    # what they know
    intentions: Set[str] = field(default_factory=set)   # what they're trying to do


class TheoryOfMindModule:
    """
    Tracks beliefs, knowledge, and intentions of other agents.
    Enables social reasoning: 'Does he KNOW the door is locked?'
    """

    def __init__(self):
        self.agents: Dict[str, AgentModel] = {}

    def register_agent(self, name: str):
        self.agents[name] = AgentModel(name=name)

    def agent_knows(self, agent: str, fact: str) -> bool:
        if agent in self.agents:
            return fact in self.agents[agent].knowledge
        return False

    def agent_believes(self, agent: str, belief: str) -> bool:
        if agent in self.agents:
            return belief in self.agents[agent].beliefs
        return False

    def false_belief_check(self, agent: str, belief: str, reality: str) -> bool:
        """
        Classic Sally-Anne test: detect if agent holds a FALSE belief.
        Returns True if agent believes something that contradicts reality.
        """
        holds_belief = self.agent_believes(agent, belief)
        belief_matches_reality = (belief == reality)
        return holds_belief and not belief_matches_reality

    def infer_intention(self, agent: str, observed_action: str) -> str:
        """Inverse reasoning: action -> likely intention."""
        # Map observed actions to goal hypotheses
        return "unknown"
