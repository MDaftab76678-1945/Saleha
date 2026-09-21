"""
Saleha Core: Technical Debt & Cognitive Complexity De-Synthesizer

Analyzes codebase ASTs to compute Cyclomatic & Cognitive Complexity per function,
identifies God Objects and deep nesting anti-patterns, and proposes modular refactorings.
"""

from __future__ import annotations

import os
import ast
from dataclasses import dataclass, field
from typing import List, Optional

from saleha.core.path_utils import safe_relpath


@dataclass
class FunctionComplexityMetric:
    file_path: str
    function_name: str
    line_number: int
    lines_of_code: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    max_nesting_depth: int
    is_hotspot: bool = False
    refactor_suggestion: str = ""


@dataclass
class CodebaseDebtReport:
    total_functions_analyzed: int
    hotspots_count: int
    average_cyclomatic: float
    max_cyclomatic: int
    hotspots: List[FunctionComplexityMetric] = field(default_factory=list)


class _ComplexityVisitor(ast.NodeVisitor):
    """Calculates branch counts and nesting levels for a function AST node."""

    def __init__(self) -> None:
        self.cyclomatic = 1
        self.cognitive = 0
        self.max_nesting = 0
        self._current_nesting = 0
        self._is_root = True

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_nested_def(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_nested_def(node)

    def _visit_nested_def(self, node) -> None:
        # Real bug found auditing this module: analyze_file() calls
        # ast.walk(tree) at module level, so a nested function is visited
        # and scored on its own -- but this visitor's generic_visit also
        # descended into that same nested function while scoring the
        # OUTER function, double-counting its branches into the outer
        # function's own complexity. Confirmed by direct probe: an outer
        # function with one real `if` (true complexity 2) scored 4 because
        # a nested helper's two `if`s got added on top. The standard
        # convention scores each function independently; a nested def is
        # a boundary this visitor must not cross, except for the very
        # first node it's given (the function it was constructed to
        # measure, which visit() always calls with).
        if self._is_root:
            self._is_root = False
            self.generic_visit(node)
        # else: a genuinely nested function -- do not descend, it is
        # scored separately by its own top-level ast.walk() visit.

    def _increase_nesting(self) -> None:
        self._current_nesting += 1
        if self._current_nesting > self.max_nesting:
            self.max_nesting = self._current_nesting

    def _decrease_nesting(self) -> None:
        self._current_nesting -= 1

    def visit_If(self, node: ast.If) -> None:
        self.cyclomatic += 1
        self.cognitive += (1 + self._current_nesting)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_For(self, node: ast.For) -> None:
        self.cyclomatic += 1
        self.cognitive += (1 + self._current_nesting)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_While(self, node: ast.While) -> None:
        self.cyclomatic += 1
        self.cognitive += (1 + self._current_nesting)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.cyclomatic += 1
        self.cognitive += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.cyclomatic += len(node.values) - 1
        self.cognitive += len(node.values) - 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        # A ternary expression branches just like an if statement does.
        self.cyclomatic += 1
        self.cognitive += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        # An assert either passes or raises -- a real branch.
        self.cyclomatic += 1
        self.cognitive += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        # Each case arm is an independent branch.
        self.cyclomatic += len(node.cases)
        self.cognitive += len(node.cases)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._count_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._count_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._count_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._count_comprehension(node)

    def _count_comprehension(self, node) -> None:
        # Each loop and each condition inside a comprehension branches.
        for gen in node.generators:
            self.cyclomatic += 1 + len(gen.ifs)
            self.cognitive += 1 + len(gen.ifs)
        self.generic_visit(node)


class TechDebtAnalyzer:
    """Calculates software metrics and flags maintainability hotspots across the codebase."""

    def __init__(self, root_dir: str = ".") -> None:
        self.root_dir = os.path.abspath(root_dir)

    @staticmethod
    def _make_suggestion(vis: _ComplexityVisitor, loc: int) -> str:
        """Returns a refactor suggestion string for a hotspot function."""
        if vis.max_nesting > 3:
            return "Flatten nested conditionals using guard clauses / early returns."
        if loc > 60:
            return f"Extract helper functions; {loc} lines violates single responsibility."
        return "Decompose boolean conditions into dedicated predicate functions."

    def analyze_file(self, file_path: str) -> List[FunctionComplexityMetric]:
        """Calculates complexity metrics for all functions in a single python file."""
        if not os.path.isfile(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                code = fp.read()
            tree = ast.parse(code, filename=file_path)
        except (SyntaxError, OSError):
            return []

        results: List[FunctionComplexityMetric] = []
        rel_p = safe_relpath(file_path, self.root_dir).replace(os.sep, "/")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                vis = _ComplexityVisitor()
                vis.visit(node)
                start_l = node.lineno
                end_l = getattr(node, "end_lineno", start_l + 5)
                loc = end_l - start_l + 1

                # Hotspot criteria: Cyclomatic > 10 OR Cognitive > 15 OR LOC > 60
                is_hot = (vis.cyclomatic > 10 or vis.cognitive > 15 or loc > 60)
                suggestion = self._make_suggestion(vis, loc) if is_hot else ""

                results.append(FunctionComplexityMetric(
                    file_path=rel_p,
                    function_name=node.name,
                    line_number=start_l,
                    lines_of_code=loc,
                    cyclomatic_complexity=vis.cyclomatic,
                    cognitive_complexity=vis.cognitive,
                    max_nesting_depth=vis.max_nesting,
                    is_hotspot=is_hot,
                    refactor_suggestion=suggestion
                ))

        return results

    def analyze_workspace(self, root_dir: Optional[str] = None, threshold: int = 10) -> CodebaseDebtReport:
        """Analyzes all Python files in the workspace."""
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)

        all_metrics: List[FunctionComplexityMetric] = []

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__", "build", "dist")]
            for f in files:
                if f.endswith(".py"):
                    full_p = os.path.join(root, f)
                    all_metrics.extend(self.analyze_file(full_p))

        if not all_metrics:
            # An empty workspace has zero complexity -- reporting 1.0 here
            # would be the vacuous-metric distortion this project forbids
            # (a value for a measurement that never ran).
            return CodebaseDebtReport(
                total_functions_analyzed=0,
                hotspots_count=0,
                average_cyclomatic=0.0,
                max_cyclomatic=0,
                hotspots=[]
            )

        hotspots = [m for m in all_metrics if m.cyclomatic_complexity >= threshold or m.is_hotspot]
        avg_cyc = round(sum(m.cyclomatic_complexity for m in all_metrics) / len(all_metrics), 1)
        max_cyc = max(m.cyclomatic_complexity for m in all_metrics)

        return CodebaseDebtReport(
            total_functions_analyzed=len(all_metrics),
            hotspots_count=len(hotspots),
            average_cyclomatic=avg_cyc,
            max_cyclomatic=max_cyc,
            hotspots=hotspots
        )


# Global instance
tech_debt_analyzer = TechDebtAnalyzer()

