"""
Saleha Core: Neuro-Symbolic Invariant Scoring Engine

Lightweight static analyzer that computes a composite "invariant confidence"
score for generated code by combining symbolic AST checks:
  - Syntactic validity (parses cleanly)
  - Structural safety heuristics (no bare `except:`, no eval/exec/compile)
  - Documentation coverage (module/function docstrings present)
  - Type-annotation coverage on function arguments
  - Branch density (proxy for structural complexity)

This is a deterministic symbolic scorer (no ML inference involved) used by
the swarm self-play arena to judge candidate code produced during
adversarial curriculum training.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List


@dataclass
class InvariantScoreResult:
    composite_score: float
    syntax_valid: bool
    safety_violations: List[str] = field(default_factory=list)
    has_docstrings: bool = False
    type_annotation_coverage: float = 0.0
    branch_density: float = 0.0


class NeuroSymbolicEngine:
    """Symbolic static analyzer producing an invariant confidence score in [0, 1]."""

    UNSAFE_CALLS = {"eval", "exec", "compile", "__import__"}

    def score_code(self, code: str) -> InvariantScoreResult:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return InvariantScoreResult(composite_score=0.0, syntax_valid=False)

        violations: List[str] = []
        func_defs = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        total_args = 0
        annotated_args = 0
        branch_nodes = 0
        total_nodes = 0
        has_docstring = bool(ast.get_docstring(tree)) or any(
            ast.get_docstring(f) for f in func_defs
        )

        for node in ast.walk(tree):
            total_nodes += 1
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append("bare_except")
            if isinstance(node, ast.Call):
                fname = getattr(node.func, "id", None)
                if fname in self.UNSAFE_CALLS:
                    violations.append(f"unsafe_call:{fname}")
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                branch_nodes += 1

        for f in func_defs:
            args = f.args.args
            total_args += len(args)
            annotated_args += sum(1 for a in args if a.annotation is not None)

        type_cov = (annotated_args / total_args) if total_args else 1.0
        branch_density = (branch_nodes / total_nodes) if total_nodes else 0.0

        # Composite scoring: weighted blend rewarding safety, docs, typing;
        # penalizing detected structural violations.
        safety_score = max(0.0, 1.0 - 0.25 * len(violations))
        composite = round(
            0.45 * safety_score
            + 0.25 * (1.0 if has_docstring else 0.4)
            + 0.30 * type_cov,
            4,
        )
        composite = max(0.0, min(1.0, composite))

        return InvariantScoreResult(
            composite_score=composite,
            syntax_valid=True,
            safety_violations=violations,
            has_docstrings=has_docstring,
            type_annotation_coverage=round(type_cov, 4),
            branch_density=round(branch_density, 4),
        )


neuro_symbolic_engine = NeuroSymbolicEngine()
