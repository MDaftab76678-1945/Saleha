"""
Saleha Core: Strict Quality Guard & AST Code Integrity Engine

Enforces 2026 production-grade software engineering standards across synthesized code:
1. AST Syntactic Correctness & Syntax Tree Validation
2. Strict Type Hint Coverage (PEP 484 / PEP 604)
3. Cognitive Complexity & Nesting Depth Limits
4. Sovereign Brand Hygiene (Blocks third-party trademark leaks)
5. Anti-Pattern & Insecure Primitives Detection (eval, exec, naked except)
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set


@dataclass
class QualityIssue:
    severity: str          # "CRITICAL" | "MAJOR" | "MINOR"
    rule_id: str
    message: str
    line_number: int = 1
    column: int = 0
    can_autofix: bool = False


@dataclass
class QualityReport:
    passed: bool
    quality_score: float   # 0.0 to 100.0
    issues: List[QualityIssue] = field(default_factory=list)
    total_functions: int = 0
    typed_functions: int = 0
    type_coverage_pct: float = 100.0
    max_nesting_depth: int = 0
    file_path: Optional[str] = None

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "CRITICAL")

    @property
    def major_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "MAJOR")

    @property
    def minor_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "MINOR")


class QualityGuard:
    """Enforces strict code quality, type annotations, and structural standards."""

    FORBIDDEN_BRAND_PATTERNS = [
        re.compile(r'\bhermes\b', re.IGNORECASE),
        re.compile(r'\bclaude\b', re.IGNORECASE),
        re.compile(r'\bkimi\b', re.IGNORECASE),
    ]

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def _calculate_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Computes maximum AST control block nesting depth."""
        nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
        max_depth = current_depth

        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_types):
                sub_depth = self._calculate_nesting_depth(child, current_depth + 1)
            else:
                sub_depth = self._calculate_nesting_depth(child, current_depth)
            if sub_depth > max_depth:
                max_depth = sub_depth

        return max_depth

    def check_code(self, code: str, file_path: Optional[str] = None) -> QualityReport:
        """Performs static AST inspection, type coverage evaluation, and hygiene checks."""
        issues: List[QualityIssue] = []
        score = 100.0

        # 1. Check for third-party brand leaks
        for pattern in self.FORBIDDEN_BRAND_PATTERNS:
            for line_idx, line in enumerate(code.splitlines(), start=1):
                # Ignore standard benchmark comparison comments or baseline strings
                if "benchmark" in line.lower() or "baseline" in line.lower() or "dataset" in line.lower():
                    continue
                match = pattern.search(line)
                if match:
                    issues.append(QualityIssue(
                        severity="CRITICAL",
                        rule_id="SOV-001",
                        message=f"Brand leak detected: '{match.group(0)}' violates sovereign naming standards.",
                        line_number=line_idx,
                        column=match.start(),
                    ))
                    score -= 20.0

        # 2. Syntax and AST Parse Check
        try:
            tree = ast.parse(code, filename=file_path or "<snippet>")
        except SyntaxError as e:
            issues.append(QualityIssue(
                severity="CRITICAL",
                rule_id="SYNTAX-001",
                message=f"Syntax error: {e.msg}",
                line_number=e.lineno or 1,
                column=e.offset or 0,
            ))
            return QualityReport(
                passed=False,
                quality_score=0.0,
                issues=issues,
                file_path=file_path,
            )

        # 3. Security and Anti-Pattern Detection
        total_functions = 0
        typed_functions = 0
        max_depth = 0

        for node in ast.walk(tree):
            # Check eval / exec
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    issues.append(QualityIssue(
                        severity="CRITICAL",
                        rule_id="SEC-001",
                        message=f"Use of dangerous dynamic execution primitive '{node.func.id}()'.",
                        line_number=node.lineno,
                        column=node.col_offset,
                    ))
                    score -= 15.0

            # Check bare except:
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    issues.append(QualityIssue(
                        severity="MAJOR",
                        rule_id="ERR-001",
                        message="Naked 'except:' caught all exceptions. Use 'except Exception:' instead.",
                        line_number=node.lineno,
                        column=node.col_offset,
                        can_autofix=True,
                    ))
                    score -= 8.0

            # Check function typing
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_functions += 1
                has_return_type = node.returns is not None
                args = node.args
                # Check parameters (excluding 'self' and 'cls')
                all_params = [a for a in args.args if a.arg not in ("self", "cls")]
                typed_params = [a for a in all_params if a.annotation is not None]
                
                is_fully_typed = has_return_type and (len(typed_params) == len(all_params))
                if is_fully_typed:
                    typed_functions += 1
                else:
                    issues.append(QualityIssue(
                        severity="MINOR",
                        rule_id="TYPE-001",
                        message=f"Function '{node.name}' lacks full type annotations (return: {has_return_type}, typed args: {len(typed_params)}/{len(all_params)}).",
                        line_number=node.lineno,
                        column=node.col_offset,
                    ))
                    score -= 4.0

                # Check function nesting depth
                func_depth = self._calculate_nesting_depth(node)
                if func_depth > max_depth:
                    max_depth = func_depth
                if func_depth > 4:
                    issues.append(QualityIssue(
                        severity="MAJOR",
                        rule_id="COMPLEX-001",
                        message=f"Excessive control-flow nesting depth ({func_depth} > 4) in function '{node.name}'.",
                        line_number=node.lineno,
                        column=node.col_offset,
                    ))
                    score -= 6.0

        type_coverage = round((typed_functions / total_functions) * 100, 1) if total_functions > 0 else 100.0
        final_score = max(0.0, min(100.0, round(score, 1)))
        passed = final_score >= 70.0 and not any(i.severity == "CRITICAL" for i in issues)

        return QualityReport(
            passed=passed,
            quality_score=final_score,
            issues=issues,
            total_functions=total_functions,
            typed_functions=typed_functions,
            type_coverage_pct=type_coverage,
            max_nesting_depth=max_depth,
            file_path=file_path,
        )

    def check_file(self, file_path: str) -> QualityReport:
        """Reads a file from disk and evaluates its code quality."""
        if not os.path.isfile(file_path):
            return QualityReport(
                passed=False,
                quality_score=0.0,
                issues=[QualityIssue(severity="CRITICAL", rule_id="IO-001", message=f"File not found: {file_path}")],
                file_path=file_path,
            )
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            return self.check_code(code, file_path=file_path)
        except OSError as e:
            return QualityReport(
                passed=False,
                quality_score=0.0,
                issues=[QualityIssue(severity="CRITICAL", rule_id="IO-002", message=f"Read error: {e}")],
                file_path=file_path,
            )

    def check_workspace(self, root_dir: str = ".", max_files: int = 50) -> Dict[str, Any]:
        """Runs quality guard scan across the workspace and returns an aggregated scorecard."""
        reports: List[QualityReport] = []
        for root, _, files in os.walk(root_dir):
            if any(p in root for p in [".git", "node_modules", ".venv", "apps", "dist", "build"]):
                continue
            for f in files:
                if f.endswith(".py") and not f.startswith("test_"):
                    full_path = os.path.join(root, f)
                    reports.append(self.check_file(full_path))
                    if len(reports) >= max_files:
                        break
            if len(reports) >= max_files:
                break

        total_files = len(reports)
        avg_score = round(sum(r.quality_score for r in reports) / total_files, 1) if total_files > 0 else 100.0
        total_critical = sum(r.critical_count for r in reports)
        total_major = sum(r.major_count for r in reports)
        avg_type_coverage = round(sum(r.type_coverage_pct for r in reports) / total_files, 1) if total_files > 0 else 100.0

        return {
            "total_files_analyzed": total_files,
            "average_quality_score": avg_score,
            "total_critical_issues": total_critical,
            "total_major_issues": total_major,
            "average_type_coverage_pct": avg_type_coverage,
            "all_passed": all(r.passed for r in reports),
        }


# Global instance
quality_guard = QualityGuard()
