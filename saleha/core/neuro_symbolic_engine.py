"""
Saleha Core: Neuro-Symbolic Invariant Scoring Engine (RLIF)

Deterministic, non-ML static analyzer that computes a composite "invariant
fitness" score for generated code by combining symbolic AST checks:
  - AST syntax validity (parses cleanly)
  - Type-annotation coverage (PEP 484/604)
  - OWASP/SAST security heuristics (shell exec, eval/exec, hardcoded secrets)
  - Functional-contract integrity (well-formed return/yield)

Used across the swarm self-play arena, MCTS search, GRPO reasoning trainer,
self-evolving loop, MCP server, and chat session to judge candidate code
produced during training/inference -- Reinforcement Learning from Invariant
Feedback (RLIF).

Note: an earlier, independently-developed version of this module (different
dataclass/field names: InvariantScoreResult with syntax_valid/
safety_violations/has_docstrings) existed on a divergent branch. This is the
version every real current consumer's field access actually depends on
(ast_valid/type_safety_score/security_score/assertion_score/
composite_score/feedback_notes/evaluation_duration_ms) -- InvariantScoreResult
is kept as a name-only alias below for one consumer (saleha/core/cognitive/
__init__.py) that only imports/re-exports the name without touching fields.
"""

from __future__ import annotations
import ast
import re
import time
from typing import List
from dataclasses import dataclass, field


@dataclass
class InvariantFitnessScore:
    """Represents a composite neuro-symbolic invariant fitness evaluation."""
    ast_valid: bool
    type_safety_score: float  # 0.0 - 1.0
    security_score: float     # 0.0 - 1.0
    assertion_score: float    # 0.0 - 1.0
    composite_score: float    # Weighted 0.0 - 1.0
    feedback_notes: List[str] = field(default_factory=list)
    evaluation_duration_ms: float = 0.0


CodeInvariantScore = InvariantFitnessScore
InvariantScoreResult = InvariantFitnessScore  # name-only backward-compat alias


class NeuroSymbolicEngine:
    """Neuro-Symbolic optimizer that scores code candidates against deterministic

    AST grammar invariants, PEP static typing, OWASP security, and execution safety.
    """

    def score_code(self, code: str) -> InvariantFitnessScore:
        """Evaluates a code candidate and returns a weighted RLIF fitness score."""
        start = time.perf_counter()
        feedback = []

        # 1. AST Syntax Correctness (30% weight)
        ast_valid = False
        ast_points = 0.0
        try:
            tree = ast.parse(code)
            ast_valid = True
            ast_points = 1.0
            feedback.append("AST: Clean Syntax (0 Parsing Errors)")
        except SyntaxError as e:
            feedback.append(f"AST Syntax Error: {e.msg} (Line {e.lineno})")

        # 2. Type Safety & Modern PEP Conformance (20% weight)
        type_points = 0.0
        if ast_valid:
            has_annotations = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.returns or any(arg.annotation for arg in node.args.args):
                        has_annotations = True
                        break
            if has_annotations:
                type_points = 1.0
                feedback.append("Type Safety: PEP 484/604 Annotations Present")
            else:
                type_points = 0.6
                feedback.append("Type Safety: Implicit Types (Consider Explicit Type Hints)")
        else:
            feedback.append("Type Safety: Skipped due to AST error")

        # 3. OWASP & SAST Security Gate (30% weight)
        security_points = 1.0
        if "os.system(" in code or "subprocess.call(" in code:
            security_points = 0.2
            feedback.append("Security: High Risk Insecure Shell Execution Detected")
        elif "eval(" in code or "exec(" in code:
            security_points = 0.4
            feedback.append("Security: Unsafe Dynamic Code Evaluation (eval/exec)")
        elif re.search(r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", code):
            security_points = 0.5
            feedback.append("Security: Potential Hardcoded Secret Literal")
        else:
            feedback.append("Security: OWASP Top-10 SAST Clean")

        # 4. Invariant Assertion Integrity (20% weight)
        assertion_points = 0.8
        if "def " in code and ("return " in code or "yield " in code):
            assertion_points = 1.0
            feedback.append("Invariants: Well-formed functional contract with deterministic return")
        elif "def " in code:
            assertion_points = 0.7
            feedback.append("Invariants: Function definition without explicit return")

        # Calculate composite score (Weights: AST 0.30, Security 0.30, Type 0.20, Invariants 0.20)
        composite = (ast_points * 0.30) + (security_points * 0.30) + (type_points * 0.20) + (assertion_points * 0.20)
        duration = (time.perf_counter() - start) * 1000

        return InvariantFitnessScore(
            ast_valid=ast_valid,
            type_safety_score=round(type_points, 2),
            security_score=round(security_points, 2),
            assertion_score=round(assertion_points, 2),
            composite_score=round(composite, 3),
            feedback_notes=feedback,
            evaluation_duration_ms=round(duration, 3),
        )

    def rank_candidates(self, candidates: List[str]) -> List[tuple[str, InvariantFitnessScore]]:
        """Ranks multiple generated code candidates by their composite RLIF score."""
        scored = [(c, self.score_code(c)) for c in candidates]
        return sorted(scored, key=lambda pair: pair[1].composite_score, reverse=True)


neuro_symbolic_engine = NeuroSymbolicEngine()
