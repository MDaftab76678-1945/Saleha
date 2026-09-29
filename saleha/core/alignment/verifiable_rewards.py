"""Saleha Alignment: Reinforcement Learning from Hardware & Verifiable Rewards (RLHVR)
and AI Constitutional Feedback (RLAIF).

Computes strictly physical, non-fabricatable rewards:
1. Hardware sandbox execution exit codes, memory consumption, and wall-clock deadlines.
2. Formal SMT mathematical contract verification via Z3 solver.
3. Static AST contract and security violation audits.
4. Constitutional multi-agent AI rubrics (security, complexity, typing).
"""

from __future__ import annotations

import ast
import secrets
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from saleha.core.sandbox.windows_job_sandbox import SandboxRunResult, WindowsJobSandbox
from saleha.core.verification.formal_smt_verifier import FormalProofContract, FormalSMTVerifier
from saleha.sandbox.ast_security_verifier import ASTContractAuditor

_COMPLETION_MARKER_PREFIX = "__saleha_run_complete__"


def _build_harness(code: str, test_code: Optional[str], marker: str) -> str:
    """Runs candidate then tests, and prints the marker only if both ran to the end.

    A candidate that exits early (sys.exit(0), os._exit(0), raise SystemExit)
    leaves the marker unprinted, so a clean exit code alone cannot pass. This
    stops accidental and lazy reward hacks; a candidate that deliberately
    introspects the harness to recover the marker is out of scope.
    """
    lines = [
        "import os, sys",
        "sys.path.insert(0, os.getcwd())",
        "_ns ={'__name__': '__main__', '__builtins__': __builtins__}",
        f"exec(compile({code!r}, '<candidate>', 'exec'), _ns)",
    ]
    if test_code:
        lines.append(f"exec(compile({test_code!r}, '<test>', 'exec'), _ns)")
    lines.append("sys.stdout.flush()")
    lines.append(f"print({marker!r}, flush=True)")
    return "\n".join(lines) + "\n"


@dataclass
class RewardSignal:
    """Strongly-typed multi-dimensional reward vector."""
    hardware_reward: float  # RLHVR: [-1.0, 1.0] from physical execution & formal proof
    ai_feedback_reward: float  # RLAIF: [0.0, 1.0] from constitutional rubrics
    human_reward: Optional[float] = None  # RLHF: [-1.0, 1.0] when human feedback is available
    composite_score: float = 0.0  # Weighted aggregate scalar in [-1.0, 1.0]
    passed_tests: bool = False
    ast_valid: bool = False
    smt_verified: bool = False
    security_clean: bool = False
    execution_time_ms: float = 0.0
    memory_limit_hit: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hardware_reward": self.hardware_reward,
            "ai_feedback_reward": self.ai_feedback_reward,
            "human_reward": self.human_reward,
            "composite_score": self.composite_score,
            "passed_tests": self.passed_tests,
            "ast_valid": self.ast_valid,
            "smt_verified": self.smt_verified,
            "security_clean": self.security_clean,
            "execution_time_ms": self.execution_time_ms,
            "memory_limit_hit": self.memory_limit_hit,
            "details": self.details,
        }


class RLHVRVerifier:
    """Hardware & Physical Verifiable Reward Evaluator."""

    def __init__(self, memory_limit_mb: int = 100, timeout_sec: float = 5.0) -> None:
        self.memory_limit_mb = memory_limit_mb
        self.timeout_sec = timeout_sec
        self.job_sandbox = WindowsJobSandbox(
            memory_limit_mb=memory_limit_mb,
            timeout_ms=int(timeout_sec * 1000),
        )
        self.smt_verifier = FormalSMTVerifier()

    def verify_code(
        self,
        code: str,
        test_code: Optional[str] = None,
        timeout_sec: Optional[float] = None,
        cwd: Optional[str] = None,
    ) -> RewardSignal:
        """Evaluates code physically against compiler, sandbox, and SMT verifier.

        The run is sandboxed in ``cwd`` when given, otherwise in a fresh
        temporary directory. Tests count as passed only when they ran to the end.
        """
        timeout = timeout_sec or self.timeout_sec
        start_time = time.perf_counter()

        # 1. AST Static Parse
        try:
            tree = ast.parse(code)
            ast_valid = True
        except SyntaxError as e:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return RewardSignal(
                hardware_reward=-1.0,
                ai_feedback_reward=0.0,
                composite_score=-1.0,
                passed_tests=False,
                ast_valid=False,
                smt_verified=False,
                security_clean=False,
                execution_time_ms=elapsed,
                details={"syntax_error": f"Syntax error at line {e.lineno}: {e.msg}"},
            )

        # 2. Static Security & AST Contract Audit
        is_safe, violations = ASTContractAuditor.audit(code, require_assertions=False)
        security_clean = is_safe and (len(violations) == 0)

        # 3. Formal SMT Verification (Z3 Solver)
        smt_verified = True
        smt_details: Dict[str, Any] = {}
        # Find functions for SMT contract checking
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        for fn_name in funcs:
            smt_res: FormalProofContract = self.smt_verifier.verify_function_contract(code, fn_name)
            smt_details[fn_name] = {
                "z3_available": smt_res.z3_available,
                "divisions_found": smt_res.divisions_found,
                "proven_safe": smt_res.divisions_proven_safe,
                "certificate": smt_res.mathematical_certificate,
            }
            if smt_res.divisions_found > smt_res.divisions_proven_safe:
                smt_verified = False

        # 4. Hardware Sandbox Execution, in a scratch directory unless the caller
        # supplies one, so candidate code never writes into the caller's cwd.
        marker = _COMPLETION_MARKER_PREFIX + secrets.token_hex(16)
        harness = _build_harness(code, test_code, marker)
        with tempfile.TemporaryDirectory(prefix="saleha_verify_", ignore_cleanup_errors=True) as scratch:
            run_dir = Path(cwd) if cwd is not None else Path(scratch)
            harness_path = Path(scratch) / f"_saleha_verify_{marker[-8:]}.py"
            harness_path.write_text(harness, encoding="utf-8")
            sandbox_res: SandboxRunResult = self.job_sandbox.run_isolated(
                [sys.executable, str(harness_path)],
                timeout_sec=timeout,
                cwd=str(run_dir),
            )

        out_lines = sandbox_res.output.splitlines()
        run_completed = bool(out_lines) and out_lines[-1].strip() == marker
        sandbox_output = "\n".join(out_lines[:-1]) if run_completed else sandbox_res.output
        sandbox_error = sandbox_res.error
        if sandbox_res.passed and not run_completed:
            sandbox_error = (
                sandbox_error + "\n" if sandbox_error else ""
            ) + "[INCOMPLETE] Process exited with code 0 before the tests ran to completion."

        passed_tests = sandbox_res.passed and run_completed
        memory_limit_hit = sandbox_res.memory_limit_hit

        # 5. Reward Calculation Formula:
        # Base reward from test execution
        if not passed_tests:
            if sandbox_res.timed_out:
                hw_reward = -0.9
            elif memory_limit_hit:
                hw_reward = -0.8
            else:
                hw_reward = -0.5
        else:
            hw_reward = 0.5
            # Execution efficiency bonus (under 500ms gets bonus)
            if sandbox_res.execution_time_ms < 500.0:
                hw_reward += 0.1
            # Security clean bonus
            if security_clean:
                hw_reward += 0.2
            # SMT verified bonus
            if smt_verified:
                hw_reward += 0.2

        hw_reward = max(-1.0, min(1.0, hw_reward))

        # 6. AI Rubric Score
        ai_auditor = RLAIFAuditor()
        ai_rubric = ai_auditor.audit_code(code)
        ai_reward = ai_rubric["composite_score"]

        # Composite score: 70% physical hardware reward + 30% AI constitutional rubric
        # When hardware fails, composite is dominated by hardware failure
        if hw_reward < 0:
            composite = hw_reward
        else:
            composite = 0.7 * hw_reward + 0.3 * ai_reward

        composite = round(max(-1.0, min(1.0, composite)), 3)

        return RewardSignal(
            hardware_reward=round(hw_reward, 3),
            ai_feedback_reward=round(ai_reward, 3),
            composite_score=composite,
            passed_tests=passed_tests,
            ast_valid=ast_valid,
            smt_verified=smt_verified,
            security_clean=security_clean,
            execution_time_ms=round(sandbox_res.execution_time_ms, 2),
            memory_limit_hit=memory_limit_hit,
            details={
                "sandbox_exit_code": sandbox_res.exit_code,
                "run_completed": run_completed,
                "sandbox_output": sandbox_output[:2000],
                "sandbox_error": sandbox_error[:2000],
                "security_violations": violations,
                "smt_checks": smt_details,
                "ai_rubric": ai_rubric,
            },
        )


class RLAIFAuditor:
    """Constitutional AI Rubric Evaluator for code alignment."""

    def audit_code(self, code: str) -> Dict[str, float]:
        """Evaluates constitutional dimensions: security, complexity, typing, defensive structure."""
        try:
            tree = ast.parse(code)
        except Exception:
            return {
                "security_score": 0.0,
                "complexity_score": 0.0,
                "type_coverage": 0.0,
                "defensive_score": 0.0,
                "composite_score": 0.0,
            }

        # 1. Security Score
        is_safe, violations = ASTContractAuditor.audit(code, require_assertions=False)
        security_score = max(0.0, 1.0 - (len(violations) * 0.3)) if not is_safe else 1.0

        # 2. Type Coverage
        total_args = 0
        typed_args = 0
        total_returns = 0
        typed_returns = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_returns += 1
                if node.returns is not None:
                    typed_returns += 1
                for arg in node.args.args:
                    if arg.arg != "self":
                        total_args += 1
                        if arg.annotation is not None:
                            typed_args += 1

        if total_args == 0 and total_returns == 0:
            type_coverage = 0.0
        else:
            arg_ratio = (typed_args / total_args) if total_args > 0 else 0.0
            ret_ratio = (typed_returns / total_returns) if total_returns > 0 else 0.0
            type_coverage = round(0.6 * arg_ratio + 0.4 * ret_ratio, 2)

        # 3. Cyclomatic Complexity Score (simpler functions score higher)
        branching_nodes = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With))
        )
        complexity_score = round(max(0.2, min(1.0, 1.0 - (branching_nodes * 0.05))), 2)

        # 4. Defensive Score (asserts, try/except, None guards)
        has_asserts = any(isinstance(n, ast.Assert) for n in ast.walk(tree))
        has_try = any(isinstance(n, ast.Try) for n in ast.walk(tree))
        defensive_score = 0.5
        if has_asserts:
            defensive_score += 0.25
        if has_try:
            defensive_score += 0.25
        defensive_score = min(1.0, defensive_score)

        # Composite score
        composite = round(
            0.35 * security_score +
            0.25 * type_coverage +
            0.20 * complexity_score +
            0.20 * defensive_score,
            3
        )

        return {
            "security_score": security_score,
            "complexity_score": complexity_score,
            "type_coverage": type_coverage,
            "defensive_score": defensive_score,
            "composite_score": composite,
        }
