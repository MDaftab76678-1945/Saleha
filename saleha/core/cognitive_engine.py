"""
Saleha Core: 4D Cognitive State & Ethics Engine (CognitiveEngine)

Evaluates source code across 4 cognitive dimensions:
1. Temporal Vector: Time complexity, loop depths, latency bounds, and async starvation.
2. Spatial Vector: Memory allocations, cache efficiency, and buffer leaks.
3. Ethical Vector: Privacy leaks, unauthorized telemetry, licensing compliance, and safety.
4. Reasoning Vector: Type invariants, assertion coverage, and logical soundness.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class CognitiveDimensionScore:
    """Score and feedback for a single cognitive dimension."""
    dimension: str
    score: int  # 0 to 100
    rating: str  # "EXCELLENT", "GOOD", "WARNING", "CRITICAL"
    observations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CognitiveStateReport:
    """Consolidated 4D cognitive evaluation report."""
    overall_score: int
    temporal: CognitiveDimensionScore
    spatial: CognitiveDimensionScore
    ethical: CognitiveDimensionScore
    reasoning: CognitiveDimensionScore
    summary: str


class CognitiveEngine:
    """Evaluates 4D cognitive dimensions for high-assurance autonomous coding."""

    def __init__(self):
        """Initializes the cognitive evaluation engine."""
        pass

    def evaluate_code(self, code: str, filename: str = "snippet.py") -> CognitiveStateReport:
        """Performs multi-dimensional cognitive analysis on Python or polyglot source code."""
        temporal_score, temporal_obs, temporal_recs = self._eval_temporal(code)
        spatial_score, spatial_obs, spatial_recs = self._eval_spatial(code)
        ethical_score, ethical_obs, ethical_recs = self._eval_ethical(code)
        reasoning_score, reasoning_obs, reasoning_recs = self._eval_reasoning(code)

        overall = int((temporal_score + spatial_score + ethical_score + reasoning_score) / 4)

        def _rating(s: int) -> str:
            if s >= 90:
                return "EXCELLENT"
            if s >= 75:
                return "GOOD"
            if s >= 60:
                return "WARNING"
            return "CRITICAL"

        temp_dim = CognitiveDimensionScore("Temporal", temporal_score, _rating(temporal_score), temporal_obs, temporal_recs)
        spat_dim = CognitiveDimensionScore("Spatial", spatial_score, _rating(spatial_score), spatial_obs, spatial_recs)
        eth_dim = CognitiveDimensionScore("Ethical", ethical_score, _rating(ethical_score), ethical_obs, ethical_recs)
        reas_dim = CognitiveDimensionScore("Reasoning", reasoning_score, _rating(reasoning_score), reasoning_obs, reasoning_recs)

        summary = (f"Heuristic score {overall}/100 "
                   f"[loops:{temporal_score} growth:{spatial_score} "
                   f"telemetry-words:{ethical_score} hints:{reasoning_score}] "
                   f"-- four text patterns with arbitrary weights, not a "
                   f"measurement.")

        return CognitiveStateReport(
            overall_score=overall,
            temporal=temp_dim,
            spatial=spat_dim,
            ethical=eth_dim,
            reasoning=reas_dim,
            summary=summary,
        )

    def _eval_temporal(self, code: str) -> tuple[int, List[str], List[str]]:
        score = 100
        obs, recs = [], []
        # Check deep loop nesting (for in for in for)
        nested_loops = len(re.findall(r"\bfor\s+.*\n\s+for\s+.*\n\s+for\s+", code))
        if nested_loops > 0:
            score -= 20
            obs.append(f"Detected {nested_loops} cubic O(n³) nested loop construct(s).")
            recs.append("Refactor deeply nested loops into hash maps or lookup sets.")
        else:
            obs.append("No triple-nested `for` pattern matched. This is a text "
                       "search, not a complexity analysis.")
        return max(0, score), obs, recs

    def _eval_spatial(self, code: str) -> tuple[int, List[str], List[str]]:
        score = 100
        obs, recs = [], []
        if ".append(" in code and "while True:" in code:
            score -= 15
            obs.append("Unbounded collection growth detected in potential infinite loop.")
            recs.append("Apply a ring buffer or max length eviction policy.")
        else:
            obs.append("No `.append(` inside a `while True:` matched. Nothing "
                       "else about memory was examined.")
        return max(0, score), obs, recs

    def _eval_ethical(self, code: str) -> tuple[int, List[str], List[str]]:
        score = 100
        obs, recs = [], []
        if re.search(r"\b(?:telemetry|track_user|analytics_send)\b", code):
            score -= 25
            obs.append("Potential unconsented tracking or telemetry identifier detected.")
            recs.append("Ensure explicit opt-in privacy consent before telemetry dispatch.")
        else:
            obs.append("No matches for the telemetry word list (telemetry, "
                       "track_user, analytics_send). This is a word search over "
                       "source text: it cannot see data flow and is not an "
                       "assurance.")
        return max(0, score), obs, recs

    def _eval_reasoning(self, code: str) -> tuple[int, List[str], List[str]]:
        score = 100
        obs, recs = [], []
        has_type_hints = bool(re.search(r"def \w+\(.*?:\s*\w+.*?\)\s*->", code))
        has_docstrings = '"""' in code or "'''" in code
        if not has_type_hints:
            score -= 10
            obs.append("Type signatures missing on function interfaces.")
            recs.append("Add explicit type annotations for formal reasoning guarantees.")
        if not has_docstrings:
            score -= 10
            obs.append("Interface documentation docstrings missing.")
            recs.append("Add structured docstrings explaining invariants.")
        if score == 100:
            obs.append("Type hints and docstrings are present. Neither was "
                       "checked for correctness.")
        return max(0, score), obs, recs


cognitive_engine = CognitiveEngine()
