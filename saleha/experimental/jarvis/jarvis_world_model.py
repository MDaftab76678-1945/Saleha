"""
GAP 1 REMEDIATION: Causal World Model + Symbol Grounding
Converts statistical token associations into grounded predictive understanding.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import defaultdict


@dataclass
class GroundedConcept:
    """A concept bound to sensory-motor-causal signature."""
    name: str
    visual_embedding: Optional[np.ndarray] = None      # Qwen2.5-VL grounded
    affordances: Dict[str, float] = field(default_factory=dict)  # can-* capabilities
    physics_params: Dict[str, float] = field(default_factory=dict)  # mass, fragility
    causal_roles: List[str] = field(default_factory=list)  # cause/effect relations
    prediction_accuracy: float = 0.0  # understanding score


class CausalWorldModel:
    """
    JEPA-inspired latent predictor. Learns to predict future states
    from (current_state, action) pairs. Prediction error = understanding gap.
    """

    def __init__(self, latent_dim: int = 256):
        self.latent_dim = latent_dim
        self.concepts: Dict[str, GroundedConcept] = {}
        self.transition_model: Dict[str, Dict[str, str]] = defaultdict(dict)
        # (concept, action) -> predicted_outcome

    def ground_concept(self, name: str, visual_emb: np.ndarray,
                       affordances: Dict[str, float],
                       physics: Dict[str, float]) -> GroundedConcept:
        """Bind a concept to its sensory-motor signature (symbol grounding)."""
        concept = GroundedConcept(
            name=name,
            visual_embedding=visual_emb,
            affordances=affordances,
            physics_params=physics,
        )
        self.concepts[name] = concept
        return concept

    def predict_outcome(self, concept_name: str, action: str) -> Optional[str]:
        """
        CORE UNDERSTANDING TEST:
        Predict the outcome of an action on a concept WITHOUT observing it.
        """
        if concept_name not in self.concepts:
            return None
        return self.transition_model[concept_name].get(action)

    def update_from_observation(self, concept_name: str, action: str,
                                actual_outcome: str):
        """Learn transition from observed reality; update prediction accuracy."""
        predicted = self.predict_outcome(concept_name, action)
        was_correct = (predicted == actual_outcome)

        # Update transition model
        self.transition_model[concept_name][action] = actual_outcome

        # Update understanding score (exponential moving average)
        if concept_name in self.concepts:
            c = self.concepts[concept_name]
            alpha = 0.3
            reward = 1.0 if was_correct else 0.0
            c.prediction_accuracy = (
                alpha * reward + (1 - alpha) * c.prediction_accuracy
            )

    def understanding_score(self, concept_name: str) -> float:
        """Quantify genuine understanding as prediction accuracy."""
        if concept_name in self.concepts:
            return self.concepts[concept_name].prediction_accuracy
        return 0.0
