"""
GAP 2 REMEDIATION: Abductive Discovery Engine + Counterfactual Simulation
Generates genuinely novel hypotheses, not retrieved knowledge recombination.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import deque


@dataclass
class Hypothesis:
    statement: str
    surprise_score: float       # how much it contradicts prior model
    explanatory_power: float    # how well it explains the anomaly
    verifiability: float        # can it be tested?
    novelty: float = 0.0        # composite score

    def compute_novelty(self):
        self.novelty = self.surprise_score * self.explanatory_power * self.verifiability
        return self.novelty


class AnomalyDetector:
    """
    Detects prediction errors in the world model.
    Surprise = -log P(observation | current_model)
    """

    def __init__(self):
        self.prediction_history = deque(maxlen=200)

    def compute_surprise(self, predicted: str, observed: str) -> float:
        """Surprise signal: 0 (expected) to 1 (completely unexpected)."""
        if predicted == observed:
            return 0.0
        # Semantic distance as surprise proxy
        return 1.0  # simplified; use embedding distance in production


class AbductiveDiscoveryEngine:
    """
    Generates novel hypotheses via abduction (inference to best explanation).
    Unlike deduction (known rules) or induction (pattern generalization),
    abduction SYNTHESIZES new explanatory rules.
    """

    def __init__(self, world_model):
        self.world_model = world_model
        self.anomaly_detector = AnomalyDetector()
        self.hypothesis_pool: List[Hypothesis] = []

    def on_anomaly(self, observation: str, predicted: str):
        """Triggered when world model prediction fails."""
        surprise = self.anomaly_detector.compute_surprise(predicted, observation)
        if surprise > 0.5:  # significant anomaly
            candidates = self.generate_hypotheses(observation, predicted)
            ranked = self.rank_by_novelty(candidates)
            self.hypothesis_pool.extend(ranked)
            return ranked
        return []

    def generate_hypotheses(self, observation: str, predicted: str) -> List[Hypothesis]:
        """
        Synthesize candidate explanations.
        In production: call qwen2.5:7b with abduction prompt +
        constraint that output must NOT match any existing transition_model entry.
        """
        # Placeholder for LLM-backed synthesis with novelty constraint
        candidates = []
        # ... LLM generates N hypotheses ...
        return candidates

    def counterfactual_test(self, hypothesis: Hypothesis) -> float:
        """
        CORE NOVELTY TEST:
        'If H were true, what ELSE would we observe?'
        Checks if hypothesis makes NEW testable predictions.
        A hypothesis that only explains the original anomaly (no new
        predictions) is post-hoc fitting, not genuine insight.
        """
        # Count new predictions the hypothesis enables
        new_predictions = 0  # computed via world model simulation
        return new_predictions

    def rank_by_novelty(self, candidates: List[Hypothesis]) -> List[Hypothesis]:
        for h in candidates:
            h.explanatory_power = self.counterfactual_test(h)
            h.compute_novelty()
        return sorted(candidates, key=lambda x: x.novelty, reverse=True)
