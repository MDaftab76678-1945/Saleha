"""
Saleha Core: a small structural causal model over a hand-written graph.

Answers "what happens to Y if X changes" against a fixed graph of six software
engineering variables (async IO, caching, test coverage -> latency, defect
rate, throughput) with hand-assigned edge weights.

## What was wrong with this before

It advertised Pearl's three-layer hierarchy -- L1 association, L2 intervention,
L3 counterfactual -- and the three layers computed the same thing.

`simulate_l2_intervention` called `query_l1_association` directly. Measured:

    L1 association  : 120.0
    L2 intervention : 120.0    <- identical, for the same inputs

The entire point of the hierarchy is that these differ. `do(X = x)` means the
graph is mutated: every incoming edge to X is severed, because X is now set by
the intervention rather than by its causes. Nothing was severed, so "doing" and
"observing" produced one number under two names.

`graph_surgery()` now performs that mutation, and `simulate_l2_intervention`
runs against the mutated graph. On this default graph the two still agree for
most queries -- the action variables are roots with no incoming edges, so there
is nothing to cut -- and the report says so explicitly via
`differs_from_association`. That is an honest "no difference here", which is
not the same as never having looked.

## What this still is not

- **The graph is hand-written, not learned.** It is six variables someone typed
  in. It is not derived from any codebase, and `causal-eval` evaluates the
  fixed graph, not the project it is pointed at.
- **The edge weights are guesses.** `-0.7` for cache-to-latency came from
  judgement, not measurement.
- **L3 is not full counterfactual inference.** Pearl's procedure is abduction
  (infer the exogenous noise from the observed facts), action, prediction. There
  is no noise model here, so abduction is skipped and the result is a
  difference between two interventions. `abduction_performed=False` records
  that rather than letting the L3 label imply otherwise.
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
    # What the same query returns WITHOUT graph surgery. When these match, the
    # intervention severed nothing (the intervened variables are graph roots),
    # and saying so is more honest than implying a difference that is not there.
    association_outcome: Optional[float] = None
    severed_edges: List[str] = field(default_factory=list)
    # L3 only. Pearl's counterfactual procedure is abduction -> action ->
    # prediction. There is no noise model here, so abduction never runs and the
    # result is a difference between two interventions.
    abduction_performed: bool = False

    @property
    def differs_from_association(self) -> bool:
        """True when graph surgery actually changed the answer."""
        return (self.association_outcome is not None
                and self.association_outcome != self.expected_outcome)


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

    def graph_surgery(self, intervened: Dict[str, Any]) -> List[CausalEdge]:
        """
        Return the edge set after do(X=x): every incoming edge to an intervened
        variable is severed.

        This is what makes intervention different from observation. Setting X
        by intervention means X is no longer produced by its causes, so those
        arrows no longer carry information about it. This step did not exist --
        `simulate_l2_intervention` called the association query directly, so
        "doing" and "observing" returned the same number.
        """
        return [e for e in self.edges if e.effect not in intervened]

    def _predict(self, evidence: Dict[str, Any], target: str,
                 edges: List[CausalEdge]) -> float:
        """Propagate `evidence` to `target` over the given edge set."""
        base = self.variables.get(
            target, CausalVariable(target, "outcome", 100.0, "")).observed_value
        if not isinstance(base, (int, float)):
            return 1.0
        val = float(base)
        for edge in edges:
            if edge.effect == target and edge.cause in evidence:
                val *= 1.0 + (edge.weight * 0.5 if evidence[edge.cause] else 0.0)
        return round(val, 2)

    def simulate_l2_intervention(self, intervention: Dict[str, Any], target: str) -> CausalEvaluationReport:
        """
        L2 Intervention: the outcome of do(X=x), computed on the mutated graph.

        The result also carries what plain association would have returned, so
        a caller can see whether the surgery changed anything. On the default
        graph the action variables are roots, so usually it does not -- and
        reporting that honestly is the point.
        """
        mutated = self.graph_surgery(intervention)
        severed = [f"{e.cause} -> {e.effect}"
                   for e in self.edges if e not in mutated]

        outcome = self._predict(intervention, target, mutated)
        assoc = self.query_l1_association(intervention, target)
        orig_val = self.variables[target].observed_value if target in self.variables else outcome
        conf = self.compute_causal_confidence(intervention, target)

        reasoning = (
            f"Applying do({intervention}) with graph surgery: target '{target}' "
            f"goes from {orig_val} to predicted {outcome} (confidence {conf}). "
        )
        if severed:
            reasoning += f"Severed incoming edges: {', '.join(severed)}. "
        else:
            reasoning += ("No edges severed -- the intervened variables have no "
                          "incoming causes in this graph, so intervening and "
                          "observing coincide here. ")

        return CausalEvaluationReport(
            inquiry_level="L2_Intervention",
            target_variable=target,
            original_state={target: orig_val},
            intervened_state=intervention,
            expected_outcome=outcome,
            confidence=conf,
            reasoning=reasoning,
            association_outcome=assoc,
            severed_edges=severed,
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
        # Pearl's L3 is abduction -> action -> prediction. There is no noise
        # model here to abduct from, so this is the difference between two
        # interventions. The flag on the report says so.
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
            reasoning=reasoning + (
                " Note: no abduction step was performed (this model has no "
                "exogenous noise term), so this is a comparison of two "
                "interventions, not full counterfactual inference."
            ),
            association_outcome=factual_outcome,
            abduction_performed=False,
        )


causal_world_model = CausalWorldModel()
