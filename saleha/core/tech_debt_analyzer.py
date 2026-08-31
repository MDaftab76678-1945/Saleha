"""
Saleha Core: Technical Debt & Cognitive Complexity De-Synthesizer

Analyzes codebase ASTs to compute Cyclomatic & Cognitive Complexity per function,
identifies God Objects and deep nesting anti-patterns, and proposes modular refactorings.
"""

from __future__ import annotations

import os
import ast
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

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

    def __init__(self):
        self.cyclomatic = 1
        self.cognitive = 0
        self.max_nesting = 0
        self._current_nesting = 0

    def _increase_nesting(self):
        self._current_nesting += 1
        if self._current_nesting > self.max_nesting:
            self.max_nesting = self._current_nesting

    def _decrease_nesting(self):
        self._current_nesting -= 1

    def visit_If(self, node: ast.If):
        self.cyclomatic += 1
        self.cognitive += (1 + self._current_nesting)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_For(self, node: ast.For):
        self.cyclomatic += 1
        self.cognitive += (1 + self._current_nesting)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_While(self, node: ast.While):
        self.cyclomatic += 1
        self.cognitive += (1 + self._current_nesting)
        self._increase_nesting()
        self.generic_visit(node)
        self._decrease_nesting()

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self.cyclomatic += 1
        self.cognitive += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        self.cyclomatic += len(node.values) - 1
        self.cognitive += len(node.values) - 1
        self.generic_visit(node)


class TechDebtAnalyzer:
    """Calculates software metrics and flags maintainability hotspots across the codebase."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

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
                suggestion = ""
                if is_hot:
                    if vis.max_nesting > 3:
                        suggestion = "Flatten nested conditionals using guard clauses / early returns."
                    elif loc > 60:
                        suggestion = f"Extract helper functions; {loc} lines violates single responsibility."
                    else:
                        suggestion = "Decompose boolean conditions into dedicated predicate functions."

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
            return CodebaseDebtReport(
                total_functions_analyzed=0,
                hotspots_count=0,
                average_cyclomatic=1.0,
                max_cyclomatic=1,
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

