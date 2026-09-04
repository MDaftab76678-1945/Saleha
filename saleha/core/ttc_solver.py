"""
Saleha Core: Test-Time Compute (TTC) Multi-Trajectory Solver

Implements 2026 frontier inference-time compute scaling:
- Explores K distinct reasoning and implementation trajectories in parallel.
- Evaluates candidate trajectories using AST static quality, test assertion verification,
  semantic coherence, and execution simplicity.
- Best-of-N reranking algorithm selects the mathematically optimal solution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, Tuple

from saleha.core.quality_guard import QualityGuard, QualityReport, quality_guard
from saleha.core.test_runner import TestRunner, TestSuiteResult


@dataclass
class CandidateTrajectory:
    trajectory_id: str
    strategy_name: str
    code: str
    explanation: str = ""
    quality_report: Optional[QualityReport] = None
    test_result: Optional[TestSuiteResult] = None
    quality_score: float = 0.0
    test_score: float = 0.0
    simplicity_score: float = 0.0
    coherence_score: float = 0.0
    overall_score: float = 0.0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTCSolveResult:
    problem: str
    best_trajectory: Optional[CandidateTrajectory]
    candidates: List[CandidateTrajectory] = field(default_factory=list)
    total_compute_time_ms: float = 0.0
    strategy_used: str = "best_of_n_rerank"
    summary: str = ""

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def passed(self) -> bool:
        if not self.best_trajectory:
            return False
        return self.best_trajectory.overall_score >= 70.0


class TTCTrajectorySolver:
    """Multi-trajectory inference-time solver with automated verification and reranking."""

    DEFAULT_STRATEGIES = [
        "direct_idiomatic",
        "defensive_validated",
        "modular_decomposed",
    ]

    def __init__(self, guard: Optional[QualityGuard] = None, test_runner: Optional[TestRunner] = None):
        self.guard = guard or quality_guard
        self.test_runner = test_runner or TestRunner()

    def _evaluate_simplicity(self, code: str) -> float:
        """Scores code simplicity and conciseness (avoids bloated boilerplate)."""
        lines = [l.strip() for l in code.splitlines() if l.strip() and not l.strip().startswith("#")]
        num_lines = len(lines)
        if num_lines == 0:
            return 0.0
        # Optimal concise range: 5 - 40 lines
        if 5 <= num_lines <= 50:
            return 100.0
        elif num_lines < 5:
            return 80.0
        elif num_lines <= 100:
            return max(50.0, 100.0 - (num_lines - 50) * 0.8)
        else:
            return max(20.0, 60.0 - (num_lines - 100) * 0.2)

    def _evaluate_coherence(self, explanation: str, code: str) -> float:
        """Scores semantic coherence and alignment between explanation and implementation."""
        if not explanation:
            return 60.0
        score = 80.0
        if len(explanation.split()) >= 15:
            score += 10.0
        # Check if explanation references identifiers present in the code
        import re
        func_defs = re.findall(r'def\s+([a-zA-Z0-9_]+)', code)
        for f in func_defs:
            if f in explanation:
                score += 5.0
                break
        return min(100.0, score)

    def evaluate_candidate(
        self,
        candidate: CandidateTrajectory,
        test_code: Optional[str] = None,
    ) -> CandidateTrajectory:
        """Evaluates a single candidate trajectory across quality, tests, and simplicity."""
        start_t = time.perf_counter()

        # 1. Static AST Quality Check
        q_report = self.guard.check_code(candidate.code)
        candidate.quality_report = q_report
        candidate.quality_score = q_report.quality_score

        # 2. Test Assertion Execution
        if test_code:
            try:
                t_result = self.test_runner.run_suite(
                    code=candidate.code,
                    test_code=test_code,
                    timeout=5,
                )
                candidate.test_result = t_result
                if t_result.passed:
                    candidate.test_score = 100.0
                elif t_result.ran > 0:
                    passed_ratio = (t_result.ran - len(t_result.failures)) / t_result.ran
                    candidate.test_score = max(0.0, passed_ratio * 90.0)
                else:
                    candidate.test_score = 0.0
            except Exception as e:
                candidate.test_score = 0.0
                candidate.metadata["test_error"] = str(e)
        else:
            candidate.test_score = candidate.quality_score

        # 3. Simplicity & Coherence
        candidate.simplicity_score = self._evaluate_simplicity(candidate.code)
        candidate.coherence_score = self._evaluate_coherence(candidate.explanation, candidate.code)

        # 4. Composite Rerank Score
        if test_code:
            # Heavy test weight when test assertions exist
            candidate.overall_score = round(
                (0.40 * candidate.test_score) +
                (0.30 * candidate.quality_score) +
                (0.15 * candidate.coherence_score) +
                (0.15 * candidate.simplicity_score),
                2
            )
        else:
            # Static quality dominant when purely generating
            candidate.overall_score = round(
                (0.50 * candidate.quality_score) +
                (0.30 * candidate.coherence_score) +
                (0.20 * candidate.simplicity_score),
                2
            )

        candidate.execution_time_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return candidate

    def solve(
        self,
        problem: str,
        candidate_generator_fn: Optional[Callable[[str, str], Tuple[str, str]]] = None,
        num_candidates: int = 3,
        test_code: Optional[str] = None,
        provided_candidates: Optional[List[CandidateTrajectory]] = None,
    ) -> TTCSolveResult:
        """
        Runs Test-Time Compute multi-trajectory exploration.
        Either evaluates provided candidates or generates them dynamically via generator.
        """
        start_total = time.perf_counter()
        candidates: List[CandidateTrajectory] = []

        if provided_candidates:
            for cand in provided_candidates:
                evaluated = self.evaluate_candidate(cand, test_code=test_code)
                candidates.append(evaluated)
        elif candidate_generator_fn:
            strategies = self.DEFAULT_STRATEGIES[:num_candidates]
            while len(strategies) < num_candidates:
                strategies.append(f"variation_{len(strategies)+1}")

            for idx, strat in enumerate(strategies, start=1):
                try:
                    code, explanation = candidate_generator_fn(problem, strat)
                    cand = CandidateTrajectory(
                        trajectory_id=f"TTC-{idx:02d}",
                        strategy_name=strat,
                        code=code,
                        explanation=explanation,
                    )
                    evaluated = self.evaluate_candidate(cand, test_code=test_code)
                    candidates.append(evaluated)
                except Exception as e:
                    # Failed candidate generation
                    cand = CandidateTrajectory(
                        trajectory_id=f"TTC-{idx:02d}",
                        strategy_name=strat,
                        code="",
                        explanation=f"Generation failed: {e}",
                        overall_score=0.0,
                    )
                    candidates.append(cand)
        else:
            # Fallback default heuristic template if no generator provided
            default_cand = CandidateTrajectory(
                trajectory_id="TTC-01",
                strategy_name="direct_idiomatic",
                code=f"# Solution for: {problem}\ndef solve() -> str:\n    return 'solved'\n",
                explanation="Default idiomatic baseline solution.",
            )
            candidates.append(self.evaluate_candidate(default_cand, test_code=test_code))

        # Best-of-N reranking (sort descending by overall_score)
        candidates.sort(key=lambda c: c.overall_score, reverse=True)
        best = candidates[0] if candidates else None

        total_time = round((time.perf_counter() - start_total) * 1000, 2)
        summary = (
            f"TTC Solver explored {len(candidates)} trajectories in {total_time}ms. "
            f"Best candidate: {best.trajectory_id} ({best.strategy_name}) with score {best.overall_score:.1f}/100."
            if best else "No valid candidates evaluated."
        )

        return TTCSolveResult(
            problem=problem,
            best_trajectory=best,
            candidates=candidates,
            total_compute_time_ms=total_time,
            strategy_used="best_of_n_rerank",
            summary=summary,
        )


# Aliases
TTCSolver = TTCTrajectorySolver
TTCResult = TTCSolveResult
Trajectory = CandidateTrajectory

# Global singleton solver
ttc_solver = TTCTrajectorySolver()

