"""
Saleha Core: Local Supremacy Engine (Small Beating Large).

Implements Step 4 of the Master Vision (Small Beating Large):
Enabling a 4GB/3B local model to outperform 200B parameter frontier models.

Empowers local-first models (e.g. Qwen2.5-Coder 3B / Qwen3 8B) to outperform single-shot
200B frontier models through Test-Time Compute (TTC) scaling:
1. Stratified Multi-Trajectory Exploration: K diverse algorithmic strategies and temperatures.
2. Dual Verification Tournament: AST syntax + security screening (0 CWEs) before execution.
3. Isolated Sandbox Execution: Physical unit test verification inside CodeExecutor.
4. Traceback-Conditioned Reflexion: Runtime error localization and iterative self-repair.
5. Honest Verification: Physical exit codes and outputs, zero fabricated greens.
"""

from __future__ import annotations

import ast
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from saleha.core.code_executor import CodeExecutor, ExecutionResult
from saleha.core.fast_inference import FastInference, InferenceRequest, InferenceResult
from saleha.core.parallel_solver import extract_code
from saleha.core.self_healing import HealingResult, SelfHealingEngine
from saleha.sandbox.ast_security_verifier import ASTContractAuditor


@dataclass
class CandidateEvaluation:
    """One candidate trajectory evaluated through the verification tournament."""

    candidate_id: str
    strategy_name: str
    temperature: float
    code: str
    syntax_valid: bool = False
    security_clean: bool = False
    security_violations: List[str] = field(default_factory=list)
    tests_passed: bool = False
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    score: float = 0.0
    error_summary: str = ""


@dataclass
class ReflexionRepair:
    """A self-correction attempt conditioned on physical sandbox failure feedback."""

    attempt_number: int
    parent_candidate_id: str
    error_type: str
    error_summary: str
    repaired_code: str
    syntax_valid: bool = False
    security_clean: bool = False
    tests_passed: bool = False
    exit_code: int = -1
    stderr: str = ""
    execution_time_ms: float = 0.0


@dataclass
class SupremacyResult:
    """Comprehensive tournament results from the Local Supremacy Engine."""

    problem: str
    test_suite: str
    winner_code: str
    winner_id: str
    passed: bool
    single_shot_passed: bool
    amplification_factor: float
    total_candidates: int
    total_repairs: int
    candidates: List[CandidateEvaluation] = field(default_factory=list)
    repairs: List[ReflexionRepair] = field(default_factory=list)
    total_duration_ms: float = 0.0
    summary: str = ""


class LocalSupremacyEngine:
    """Test-time compute scaling and verification tournament engine for local models."""

    STRATEGIES = [
        ("direct_idiomatic", 0.2, "Write the cleanest, most direct Python implementation using standard library idioms."),
        ("defensive_guarded", 0.4, "Write a defensive, robust implementation with strict boundary checks, input validation, and type guards."),
        ("modular_decomposed", 0.6, "Decompose the solution into small, well-named helper functions leading into a concise main function."),
        ("algorithmic_optimized", 0.8, "Focus on optimal algorithmic time/space complexity, data structure efficiency, and boundary correctness."),
    ]

    def __init__(
        self,
        model: str = "qwen2.5-coder:3b",
        num_trajectories: int = 4,
        max_refinements: int = 2,
        timeout_sec: float = 60.0,
        inference: Optional[FastInference] = None,
        executor: Optional[CodeExecutor] = None,
    ) -> None:
        self.model = model
        self.num_trajectories = max(1, min(num_trajectories, 8))
        self.max_refinements = max(0, max_refinements)
        self.timeout_sec = timeout_sec
        self.inference = inference
        self.executor = executor or CodeExecutor(timeout=int(timeout_sec))
        self.healer = SelfHealingEngine()

    def _generate_candidate_batch(
        self,
        problem: str,
        num_candidates: int,
    ) -> List[Tuple[str, str, float, str]]:
        """
        Generates candidate trajectories concurrently.
        Returns tuples of (candidate_id, strategy_name, temperature, code).
        """
        is_mock = os.getenv("SALEHA_TEST_MODE") == "1" or self.model == "mock"
        if is_mock and self.inference is None:
            # Deterministic test mode generator for offline verification
            candidates = []
            for idx in range(num_candidates):
                strat_name, temp, _ = self.STRATEGIES[idx % len(self.STRATEGIES)]
                cid = f"TRAJ-{idx + 1:02d}"
                # Emit minimal Python code for tests
                code = f"def solve(x):\n    # {strat_name} implementation\n    return x\n"
                candidates.append((cid, strat_name, temp, code))
            return candidates

        engine = self.inference or FastInference()
        requests: List[InferenceRequest] = []

        for idx in range(num_candidates):
            strat_name, temp, strat_instruction = self.STRATEGIES[idx % len(self.STRATEGIES)]
            cid = f"TRAJ-{idx + 1:02d}"
            prompt = (
                f"You are an expert Python software engineer.\n"
                f"Task:\n{problem}\n\n"
                f"Engineering Approach ({strat_name}):\n{strat_instruction}\n\n"
                f"Respond with only the complete, executable Python code in a single ```python ... ``` block."
            )
            requests.append(
                InferenceRequest(
                    prompt=prompt,
                    model=self.model,
                    options={"temperature": temp, "num_predict": 1500},
                    tag=cid,
                )
            )

        results: List[InferenceResult] = engine.run_batch(requests, use_cache=False)
        candidates = []
        for idx, (req, res) in enumerate(zip(requests, results)):
            strat_name, temp, _ = self.STRATEGIES[idx % len(self.STRATEGIES)]
            cid = req.tag or f"TRAJ-{idx + 1:02d}"
            code = extract_code(res.content) if res.success else ""
            candidates.append((cid, strat_name, temp, code))

        return candidates

    def evaluate_candidate(
        self,
        candidate_id: str,
        strategy_name: str,
        temperature: float,
        code: str,
        test_suite: str,
    ) -> CandidateEvaluation:
        """Evaluates a code candidate through AST syntax, AST security, and physical sandbox tests."""
        start_t = time.perf_counter()
        clean_code = (code or "").strip()

        if not clean_code:
            return CandidateEvaluation(
                candidate_id=candidate_id,
                strategy_name=strategy_name,
                temperature=temperature,
                code="",
                syntax_valid=False,
                security_clean=False,
                tests_passed=False,
                error_summary="Empty code candidate.",
                execution_time_ms=0.0,
            )

        # Level 1: AST Syntax Validation
        try:
            ast.parse(clean_code)
            syntax_valid = True
        except SyntaxError as e:
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return CandidateEvaluation(
                candidate_id=candidate_id,
                strategy_name=strategy_name,
                temperature=temperature,
                code=clean_code,
                syntax_valid=False,
                security_clean=False,
                tests_passed=False,
                error_summary=f"SyntaxError: {e}",
                execution_time_ms=latency_ms,
            )

        # Level 2: AST Security Pre-filtering
        is_clean, violations = ASTContractAuditor.audit(clean_code, require_assertions=False)
        if not is_clean:
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return CandidateEvaluation(
                candidate_id=candidate_id,
                strategy_name=strategy_name,
                temperature=temperature,
                code=clean_code,
                syntax_valid=True,
                security_clean=False,
                security_violations=violations,
                tests_passed=False,
                error_summary=f"Security violation: {'; '.join(violations)}",
                execution_time_ms=latency_ms,
            )

        # Level 3: Isolated Sandbox Test Execution
        if test_suite.strip():
            verification_script = f"{clean_code}\n\n# Verification Test Suite\n{test_suite}\n"
        else:
            verification_script = clean_code

        exec_res: ExecutionResult = self.executor.execute(verification_script)
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

        # Calculate composite evaluation score
        score = 0.0
        if syntax_valid:
            score += 20.0
        if is_clean:
            score += 20.0
        if exec_res.success:
            score += 60.0
        elif exec_res.exit_code == 0:
            score += 40.0

        error_msg = ""
        if not exec_res.success:
            error_msg = exec_res.error or exec_res.output or f"Process failed with exit code {exec_res.exit_code}"

        return CandidateEvaluation(
            candidate_id=candidate_id,
            strategy_name=strategy_name,
            temperature=temperature,
            code=clean_code,
            syntax_valid=syntax_valid,
            security_clean=is_clean,
            security_violations=violations,
            tests_passed=exec_res.success,
            exit_code=exec_res.exit_code,
            stdout=exec_res.output,
            stderr=exec_res.error,
            execution_time_ms=latency_ms,
            score=score,
            error_summary=error_msg[:200],
        )

    def _execute_reflexion_repair(
        self,
        base_cand: CandidateEvaluation,
        problem: str,
        test_suite: str,
        attempt: int,
    ) -> Tuple[ReflexionRepair, Optional[CandidateEvaluation]]:
        """
        Executes a targeted reflexion self-repair round using physical error feedback.
        """
        start_t = time.perf_counter()
        heal_result: HealingResult = self.healer.analyze_and_heal(
            error_log=base_cand.stderr or base_cand.stdout or base_cand.error_summary,
            original_task=problem,
        )

        error_summary = (
            f"{heal_result.error_type}: {heal_result.root_cause_hint}"
            if heal_result.error_detected
            else (base_cand.error_summary or "Test execution assertion failed.")
        )

        repair_prompt = (
            f"You are fixing a defect in your previous Python implementation.\n\n"
            f"Problem:\n{problem}\n\n"
            f"Previous Implementation:\n```python\n{base_cand.code}\n```\n\n"
            f"Failure Diagnostics:\n{error_summary}\n"
            f"Error Traceback:\n{base_cand.stderr or base_cand.stdout}\n\n"
            f"Instructions:\n"
            f"1. Analyze why the failure occurred.\n"
            f"2. Fix the defect while preserving the correct logic.\n"
            f"3. Return only the complete corrected Python code in ```python ... ```."
        )

        is_mock = os.getenv("SALEHA_TEST_MODE") == "1" or self.model == "mock"
        if is_mock and self.inference is None:
            repaired_code = f"{base_cand.code}\n# Repaired attempt {attempt}\n"
        else:
            engine = self.inference or FastInference()
            req = InferenceRequest(
                prompt=repair_prompt,
                model=self.model,
                options={"temperature": 0.2, "num_predict": 1500},
            )
            res = engine.run(req, use_cache=False)
            repaired_code = extract_code(res.content) if res.success else ""

        repaired_eval = self.evaluate_candidate(
            candidate_id=f"{base_cand.candidate_id}-R{attempt}",
            strategy_name=f"{base_cand.strategy_name}-reflexion",
            temperature=0.2,
            code=repaired_code,
            test_suite=test_suite,
        )

        repair_record = ReflexionRepair(
            attempt_number=attempt,
            parent_candidate_id=base_cand.candidate_id,
            error_type=heal_result.error_type if heal_result.error_detected else "AssertionError",
            error_summary=error_summary,
            repaired_code=repaired_code,
            syntax_valid=repaired_eval.syntax_valid,
            security_clean=repaired_eval.security_clean,
            tests_passed=repaired_eval.tests_passed,
            exit_code=repaired_eval.exit_code,
            stderr=repaired_eval.stderr,
            execution_time_ms=round((time.perf_counter() - start_t) * 1000, 2),
        )

        return repair_record, repaired_eval

    def solve(
        self,
        problem: str,
        test_suite: str = "",
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> SupremacyResult:
        """
        Executes full Test-Time Compute (TTC) tournament and Reflexion repair search.
        """
        start_all = time.perf_counter()

        if callback:
            callback({
                "type": "mission_start",
                "problem": problem,
                "model": self.model,
                "trajectories": self.num_trajectories,
            })

        # Phase 1: Generate stratified candidate batch
        raw_candidates = self._generate_candidate_batch(problem, self.num_trajectories)

        # Phase 2: Run verification tournament on all candidates
        evaluations: List[CandidateEvaluation] = []
        winner: Optional[CandidateEvaluation] = None

        for cid, strat_name, temp, code in raw_candidates:
            eval_res = self.evaluate_candidate(
                candidate_id=cid,
                strategy_name=strat_name,
                temperature=temp,
                code=code,
                test_suite=test_suite,
            )
            evaluations.append(eval_res)

            if callback:
                callback({
                    "type": "candidate_evaluated",
                    "candidate": eval_res,
                })

            # Fast Pass: If this candidate passed all tests, we found an immediate winner
            if eval_res.tests_passed and winner is None:
                winner = eval_res

        single_shot_passed = bool(evaluations and evaluations[0].tests_passed)
        repairs: List[ReflexionRepair] = []

        # Phase 3: Traceback-Conditioned Reflexion (if no candidate passed tests)
        if winner is None and self.max_refinements > 0 and evaluations:
            # Pick the highest-scoring candidate with valid syntax to repair
            viable = [c for c in evaluations if c.syntax_valid and c.security_clean]
            target = viable[0] if viable else evaluations[0]

            for attempt in range(1, self.max_refinements + 1):
                if callback:
                    callback({
                        "type": "reflexion_started",
                        "attempt": attempt,
                        "target_candidate": target.candidate_id,
                    })

                repair_rec, repaired_eval = self._execute_reflexion_repair(
                    base_cand=target,
                    problem=problem,
                    test_suite=test_suite,
                    attempt=attempt,
                )
                repairs.append(repair_rec)

                if callback:
                    callback({
                        "type": "reflexion_completed",
                        "repair": repair_rec,
                    })

                if repaired_eval and repaired_eval.tests_passed:
                    winner = repaired_eval
                    evaluations.append(repaired_eval)
                    break

        # If still no winner passed tests, select the highest-scoring candidate honestly
        if winner is None:
            sorted_candidates = sorted(evaluations, key=lambda c: c.score, reverse=True)
            winner = sorted_candidates[0] if sorted_candidates else CandidateEvaluation(
                candidate_id="NONE",
                strategy_name="none",
                temperature=0.0,
                code="",
            )

        total_duration = round((time.perf_counter() - start_all) * 1000, 2)
        passed = winner.tests_passed

        # Calculate empirical amplification factor
        if single_shot_passed and passed:
            amplification = 1.0
        elif (not single_shot_passed) and passed:
            amplification = float("inf")
        else:
            amplification = 0.0

        amp_str = "+100% (recovered from 0% single-shot failure)" if amplification == float("inf") else f"{amplification:.1f}x"

        summary = (
            f"Local Supremacy Engine evaluated {len(evaluations)} trajectories across {self.model}. "
            f"Tournament Winner: {winner.candidate_id} ({winner.strategy_name}) with status "
            f"{'PASSED' if passed else 'FAILED'}. Amplification Factor: {amp_str} in {total_duration}ms."
        )

        return SupremacyResult(
            problem=problem,
            test_suite=test_suite,
            winner_code=winner.code,
            winner_id=winner.candidate_id,
            passed=passed,
            single_shot_passed=single_shot_passed,
            amplification_factor=amplification,
            total_candidates=len(raw_candidates),
            total_repairs=len(repairs),
            candidates=evaluations,
            repairs=repairs,
            total_duration_ms=total_duration,
            summary=summary,
        )


# Global singleton
local_supremacy_engine = LocalSupremacyEngine()
