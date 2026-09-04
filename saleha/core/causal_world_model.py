"""
Saleha Core: Pearl's Structural Causal World Model (CausalWorldModel)

Implements Judea Pearl's 3-layer causal hierarchy for software engineering:
1. L1 Association (Observing): P(Outcome | Evidence) correlation analysis.
2. L2 Intervention (Doing): P(Outcome | do(Variable=Value)) causal action simulation.
3. L3 Counterfactuals (Imagining): P(Outcome_{x'} | Evidence) counterfactual retrospective.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class CausalVariable:
    """Represents a node in the Structural Causal Model (SCM)."""
    name: str
    variable_type: str  # "action", "intermediate", "outcome"
    observed_value: Any
    description: str


@dataclass
class CausalEdge:
    """Directed causal relationship between two variables with effect weight."""
    cause: str
    effect: str
    weight: float  # -1.0 to 1.0
    mechanism: str


@dataclass
class CausalEvaluationReport:
    """Result of a causal inquiry across L1, L2, and L3."""
    inquiry_level: str  # "L1_Association", "L2_Intervention", "L3_Counterfactual"
    target_variable: str
    original_state: Dict[str, Any]
    intervened_state: Dict[str, Any]
    expected_outcome: float
    confidence: float
    reasoning: str


class CausalWorldModel:
    """Structural Causal Model (SCM) Engine for Software Engineering Reasoning."""

    def __init__(self):
        """Initializes the causal graph with standard software engineering dynamics."""
        self.variables: Dict[str, CausalVariable] = {}
        self.edges: List[CausalEdge] = []
        self._init_default_causal_graph()

    def _init_default_causal_graph(self):
        """Initializes baseline causal relationships."""
        self.variables = {
            "use_async_io": CausalVariable("use_async_io", "action", False, "Whether asynchronous IO is used"),
            "has_memory_cache": CausalVariable("has_memory_cache", "action", False, "Whether in-memory caching is enabled"),
            "high_test_coverage": CausalVariable("high_test_coverage", "action", True, "Whether 90%+ unit test coverage exists"),
            "latency_ms": CausalVariable("latency_ms", "outcome", 150.0, "API response latency in milliseconds"),
            "defect_rate": CausalVariable("defect_rate", "outcome", 0.02, "Production defect rate percentage"),
            "throughput_rps": CausalVariable("throughput_rps", "outcome", 200.0, "Requests per second throughput"),
        }
        self.edges = [
            CausalEdge("use_async_io", "throughput_rps", 0.8, "Async event loop increases concurrent IO capacity"),
            CausalEdge("use_async_io", "latency_ms", -0.4, "Non-blocking execution reduces waiting latency"),
            CausalEdge("has_memory_cache", "latency_ms", -0.7, "Cache hits bypass database round trips"),
            CausalEdge("high_test_coverage", "defect_rate", -0.85, "Comprehensive assertions catch regression faults"),
        ]

    def query_l1_association(self, evidence: Dict[str, Any], target: str) -> float:
        """L1 Association: Calculates expected target value given observed evidence."""
        base_val = self.variables.get(target, CausalVariable(target, "outcome", 100.0, "")).observed_value
        if not isinstance(base_val, (int, float)):
            return 1.0

        val = float(base_val)
        for edge in self.edges:
            if edge.effect == target and edge.cause in evidence:
                factor = 1.0 + (edge.weight * 0.5 if evidence[edge.cause] else 0.0)
                val *= factor
        return round(val, 2)

    def compute_causal_confidence(self, evidence: Dict[str, Any], target: str) -> float:
        """Calculates dynamic causal confidence based on incoming edge coverage and weights."""
        incoming = [e for e in self.edges if e.effect == target]
        if not incoming:
            return 0.50

        total_weight = sum(abs(e.weight) for e in incoming)
        if total_weight == 0:
            return 0.50

        covered_weight = sum(abs(e.weight) for e in incoming if e.cause in evidence)
        coverage_ratio = min(1.0, max(0.0, covered_weight / total_weight))
        return round(0.65 + (coverage_ratio * 0.30), 2)

    def simulate_l2_intervention(self, intervention: Dict[str, Any], target: str) -> CausalEvaluationReport:
        """L2 Intervention: Computes causal outcome of do(X=x) intervention."""
        outcome = self.query_l1_association(intervention, target)
        orig_val = self.variables[target].observed_value if target in self.variables else outcome
        conf = self.compute_causal_confidence(intervention, target)

        reasoning = (
            f"Applying causal intervention do({intervention}): target '{target}' "
            f"transitions from {orig_val} to predicted {outcome} (causal confidence: {conf})."
        )

        return CausalEvaluationReport(
            inquiry_level="L2_Intervention",
            target_variable=target,
            original_state={target: orig_val},
            intervened_state=intervention,
            expected_outcome=outcome,
            confidence=conf,
            reasoning=reasoning,
        )

    def evaluate_l3_counterfactual(
        self,
        factual_state: Dict[str, Any],
        counterfactual_action: Dict[str, Any],
        target: str,
    ) -> CausalEvaluationReport:
        """L3 Counterfactual: What would have happened to target if we had chosen counterfactual_action?"""
        factual_outcome = self.query_l1_association(factual_state, target)
        counterfactual_outcome = self.query_l1_association(counterfactual_action, target)
        f_conf = self.compute_causal_confidence(factual_state, target)
        cf_conf = self.compute_causal_confidence(counterfactual_action, target)
        conf = round((f_conf + cf_conf) / 2.0, 2)

        delta = round(counterfactual_outcome - factual_outcome, 2)
        reasoning = (
            f"Counterfactual Analysis: Given factual outcome={factual_outcome}, "
            f"if {counterfactual_action} had occurred instead, '{target}' would have been "
            f"{counterfactual_outcome} (Delta: {delta:+}, causal confidence: {conf})."
        )

        return CausalEvaluationReport(
            inquiry_level="L3_Counterfactual",
            target_variable=target,
            original_state=factual_state,
            intervened_state=counterfactual_action,
            expected_outcome=counterfactual_outcome,
            confidence=conf,
            reasoning=reasoning,
        )


causal_world_model = CausalWorldModel()


if __name__ == "__main__":
    _cwm = CausalWorldModel()
    _rep = _cwm.simulate_l2_intervention({"use_async_io": True, "has_memory_cache": True}, "latency_ms")
