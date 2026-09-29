"""Saleha Core: Verified Iterative Self-Correction & Lyapunov Stability Engine.

Closed-loop debugging inside an Agent Personal Computer (AgentPC):
1. Runs the code and its tests through RLHVRVerifier with the AgentPC workspace
   as the working directory.
2. Classifies the failure with SelfHealingEngine.
3. Builds repair candidates: three canned AST transforms (auto-import,
   division-by-zero returns 0, None arguments return None) plus an optional
   external generator. Canned transforms change semantics; every applied
   strategy is named in the result so a caller can see what was done.
4. Ranks candidates with the heuristic ProcessRewardModel, then re-verifies.
5. Stability (.agents/rules/lyapunov_stability.md): a candidate already tried is
   never retried, and an identical error on two consecutive steps triggers a
   phase reset to the baseline checkpoint. A reset needs an external generator
   to supply a new strategy; without one, or with no untried candidate left,
   the loop aborts and reports ATTRACTOR_TRAPPED_ABORTED.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from saleha.core.alignment.prm_mcts_engine import ProcessRewardModel
from saleha.core.alignment.verifiable_rewards import RewardSignal, RLHVRVerifier
from saleha.core.loop.self_healing import HealingResult, SelfHealingEngine
from saleha.core.sandbox.agent_pc import AgentPC

PatchFn = Callable[[str, str, str], str]


@dataclass
class CorrectionIteration:
    """Audit entry for a single self-correction attempt."""
    iteration_index: int
    strategy: str
    candidate_code: str
    error_signature: str
    prm_step_score: float
    sandbox_passed: bool
    hardware_reward: float
    code_hash: str
    phase_reset_triggered: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class CorrectionResult:
    """The physical outcome of an autonomous self-correction loop."""
    success: bool
    repaired_code: str
    initial_code: str
    iterations_count: int
    error_history: List[str]
    final_reward: Optional[RewardSignal]
    lyapunov_status: str  # "STABLE_CONVERGED", "PHASE_RESET_RECOVERED", "ATTRACTOR_TRAPPED_ABORTED"
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "repaired_code": self.repaired_code,
            "iterations_count": self.iterations_count,
            "error_history": self.error_history,
            "final_reward": self.final_reward.to_dict() if self.final_reward else None,
            "lyapunov_status": self.lyapunov_status,
            "duration_ms": self.duration_ms,
            "details": self.details,
        }


def _sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class VerifiedSelfCorrectionEngine:
    """Autonomous verified self-correction engine with Lyapunov stability enforcement."""

    def __init__(
        self,
        pc: Optional[AgentPC] = None,
        max_iterations: int = 4,
        verifier: Optional[RLHVRVerifier] = None,
    ) -> None:
        self.pc = pc or AgentPC(agent_role="self_corrector")
        self.max_iterations = max(1, min(max_iterations, 6))
        self.verifier = verifier or RLHVRVerifier()
        self.healing_engine = SelfHealingEngine()
        self.prm = ProcessRewardModel()

    def _verify(self, code: str, test_code: str) -> RewardSignal:
        return self.verifier.verify_code(
            code, test_code=test_code, cwd=str(self.pc.workspace.root_path)
        )

    def correct_code(
        self,
        failing_code: str,
        test_code: str,
        task_description: str = "",
        external_patch_fn: Optional[PatchFn] = None,
    ) -> CorrectionResult:
        """Runs iterative self-correction loop inside isolated AgentPC workspace."""
        start_time = time.perf_counter()

        self.pc.write_in_pc("solution.py", failing_code)
        self.pc.write_in_pc("test_solution.py", test_code)
        initial_ckpt = self.pc.checkpoint_pc("baseline_pre_correction")

        sig = self._verify(failing_code, test_code)
        if sig.passed_tests:
            return CorrectionResult(
                success=True,
                repaired_code=failing_code,
                initial_code=failing_code,
                iterations_count=0,
                error_history=[],
                final_reward=sig,
                lyapunov_status="STABLE_CONVERGED",
                duration_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
                details={"message": "Code already passed baseline sandbox verification.", "iterations": []},
            )

        current_code = failing_code
        iterations: List[CorrectionIteration] = []
        error_history: List[str] = []
        tried_hashes: Set[str] = {_sha(failing_code)}
        phase_reset_used = False
        abort_reason = f"Reached max_iterations={self.max_iterations} without a passing candidate."

        for step in range(1, self.max_iterations + 1):
            raw_err = sig.details.get("sandbox_error", "") or sig.details.get("syntax_error", "")
            healing_res = self.healing_engine.analyze_and_heal(raw_err, task_description)
            err_sig = f"{healing_res.error_type}:{healing_res.root_cause_hint}"
            error_history.append(err_sig)

            phase_reset = len(error_history) >= 2 and error_history[-1] == error_history[-2]
            notes: List[str] = []
            if phase_reset:
                if external_patch_fn is None:
                    abort_reason = (
                        f"Identical error on consecutive steps ({err_sig}) and no external "
                        "patch generator to supply a new strategy."
                    )
                    break
                self.pc.restore_pc(initial_ckpt)
                phase_reset_used = True
                candidates = self._external_candidates(
                    failing_code, healing_res, test_code, external_patch_fn, notes
                )
            else:
                candidates = self._generate_repair_candidates(
                    current_code, healing_res, test_code, external_patch_fn, notes
                )

            untried = [(name, code) for name, code in candidates if _sha(code) not in tried_hashes]
            if not untried:
                abort_reason = (
                    f"No untried repair candidate for {healing_res.error_type or 'unclassified error'}."
                    + (" " + " ".join(notes) if notes else "")
                )
                break

            strategy, current_code, step_prm = self._rank_by_prm(untried)
            tried_hashes.add(_sha(current_code))
            self.pc.write_in_pc("solution.py", current_code)

            sig = self._verify(current_code, test_code)
            iterations.append(
                CorrectionIteration(
                    iteration_index=step,
                    strategy=strategy,
                    candidate_code=current_code,
                    error_signature=err_sig,
                    prm_step_score=step_prm,
                    sandbox_passed=sig.passed_tests,
                    hardware_reward=sig.hardware_reward,
                    code_hash=_sha(current_code),
                    phase_reset_triggered=phase_reset,
                    notes=notes,
                )
            )

            if sig.passed_tests:
                return CorrectionResult(
                    success=True,
                    repaired_code=current_code,
                    initial_code=failing_code,
                    iterations_count=len(iterations),
                    error_history=error_history,
                    final_reward=sig,
                    lyapunov_status="PHASE_RESET_RECOVERED" if phase_reset_used else "STABLE_CONVERGED",
                    duration_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
                    details={
                        "strategies_applied": [i.strategy for i in iterations],
                        "iterations": [i.__dict__ for i in iterations],
                    },
                )

        return CorrectionResult(
            success=False,
            repaired_code=current_code,
            initial_code=failing_code,
            iterations_count=len(iterations),
            error_history=error_history,
            final_reward=sig,
            lyapunov_status="ATTRACTOR_TRAPPED_ABORTED",
            duration_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            details={
                "abort_reason": abort_reason,
                "strategies_applied": [i.strategy for i in iterations],
                "iterations": [i.__dict__ for i in iterations],
            },
        )

    def _rank_by_prm(self, candidates: List[Tuple[str, str]]) -> Tuple[str, str, float]:
        """Picks the candidate with the highest mean heuristic PRM step score."""
        best: Tuple[str, str, float] = (candidates[0][0], candidates[0][1], -1.0)
        for name, code in candidates:
            steps = self.prm.decompose_code_to_steps(code)
            avg_prm = sum(s.prm_score for s in steps) / max(1, len(steps))
            if avg_prm > best[2]:
                best = (name, code, avg_prm)
        return best[0], best[1], max(0.0, best[2])

    def _external_candidates(
        self,
        code: str,
        healing_res: HealingResult,
        test_code: str,
        external_patch_fn: PatchFn,
        notes: List[str],
    ) -> List[Tuple[str, str]]:
        try:
            patch = external_patch_fn(code, healing_res.reflexion_prompt, test_code)
        except Exception as exc:
            notes.append(f"external_patch_fn raised {type(exc).__name__}: {exc}")
            return []
        if not patch:
            notes.append("external_patch_fn returned no code.")
            return []
        return [("external_patch", patch)]

    def _generate_repair_candidates(
        self,
        code: str,
        healing_res: HealingResult,
        test_code: str,
        external_patch_fn: Optional[PatchFn],
        notes: List[str],
    ) -> List[Tuple[str, str]]:
        """Returns (strategy, code) repair candidates for the classified defect."""
        candidates: List[Tuple[str, str]] = []

        if healing_res.error_type in ("ImportError", "NameError"):
            patched = self.healing_engine.auto_patch_code(code)
            if patched and patched != code:
                candidates.append(("auto_import", patched))

        if healing_res.error_type == "ZeroDivisionError":
            patched = self._patch_zero_division(code)
            if patched:
                candidates.append(("zero_division_returns_0", patched))

        if healing_res.error_type in ("TypeError", "AttributeError"):
            patched = self._patch_none_guard(code)
            if patched:
                candidates.append(("none_args_return_none", patched))

        if external_patch_fn is not None:
            candidates.extend(
                self._external_candidates(code, healing_res, test_code, external_patch_fn, notes)
            )

        return candidates

    def _patch_zero_division(self, code: str) -> Optional[str]:
        """Rewrites `a / b` (also //, %) as `(a / b) if b != 0 else 0`."""
        try:
            tree = ast.parse(code)
            class DivProtector(ast.NodeTransformer):
                def visit_BinOp(self, node: ast.BinOp) -> Any:
                    self.generic_visit(node)
                    if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                        test_cmp = ast.Compare(
                            left=copy.deepcopy(node.right),
                            ops=[ast.NotEq()],
                            comparators=[ast.Constant(value=0)],
                        )
                        return ast.IfExp(
                            test=test_cmp,
                            body=copy.deepcopy(node),
                            orelse=ast.Constant(value=0),
                        )
                    return node
            new_tree = DivProtector().visit(tree)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        except Exception:
            return None

    def _patch_none_guard(self, code: str) -> Optional[str]:
        """Injects `if arg is None: return None` at the start of top-level functions."""
        try:
            tree = ast.parse(code)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    guard_stmts: List[ast.stmt] = []
                    for arg in node.args.args:
                        if arg.arg != "self":
                            guard = ast.If(
                                test=ast.Compare(
                                    left=ast.Name(id=arg.arg, ctx=ast.Load()),
                                    ops=[ast.Is()],
                                    comparators=[ast.Constant(value=None)]
                                ),
                                body=[ast.Return(value=ast.Constant(value=None))],
                                orelse=[],
                            )
                            guard_stmts.append(guard)
                    if guard_stmts:
                        node.body = guard_stmts + node.body
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except Exception:
            return None
