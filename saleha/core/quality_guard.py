"""
Saleha Core: AST-based code quality checks.

The analysis here is real -- it parses the code and responds to what it finds.
Three things around it were not, and are fixed:

**1. The "sovereign brand hygiene" rule is removed.** `SOV-001` matched the
bare words "claude", "hermes" or "kimi" anywhere in a file and raised a
CRITICAL that dropped 20 points and set `passed=False`. Measured on ordinary
code:

    r = requests.post("http://localhost:11434/api/generate",
                      json={"model": "claude-opus-5", "prompt": prompt})

    -> score 80.0, passed False,
       CRITICAL SOV-001 "Brand leak detected: 'claude'"

That matters because `ttc_solver.py` uses this score to pick between candidate
solutions: a correct candidate could lose to a worse one for naming the model
it sends a request to. **You cannot call a model without naming it.**

The rule was also foreign to this project. "hermes" and "kimi" appear nowhere
else in the repository -- the word list was carried in from somewhere else and
never questioned. A quality guard is for correctness and safety; what a string
says is neither, and there was no real defect for this rule to catch.

**2. The score clamped at 0.0.** Twenty-five untyped functions and four
hundred both scored 0.0, so below a certain point the number carried no
information. `raw_score` keeps the uncapped value.

**3. `check_workspace` reported a sample as a total.** It stopped at
`max_files` (default 50) wherever `os.walk` happened to reach and returned
`all_passed` over that slice with no indication it was partial. The result now
says how many files exist and whether the scan was truncated.
"""

from __future__ import annotations

import ast
import builtins
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set, Sequence, Union

_BUILTIN_NAMES: Set[str] = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__annotations__",
    "__builtins__", "__loader__", "__spec__", "__path__", "__cached__",
}


def _collect_target_names(node: ast.AST, names_set: Set[str]) -> None:
    if isinstance(node, ast.Name):
        names_set.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            _collect_target_names(elt, names_set)
    elif isinstance(node, ast.Starred):
        _collect_target_names(node.value, names_set)


def _collect_module_level_bindings(stmts: Sequence[ast.stmt], names_set: Set[str]) -> None:
    """Collects every name bound at module scope, descending into `if`/`try`/
    `for`/`while`/`with` bodies -- unlike a function or class, these do NOT
    open a new scope in Python, so `if __name__ == "__main__": x = 1` binds
    `x` at module level, not inside some inaccessible sub-scope.

    Without this, any module-level `if __name__ == "__main__":` block (the
    single most common pattern in this codebase's own files) scored every
    name it assigned as a false CRITICAL UNDEF-001, because the caller only
    ever scanned direct top-level statements.
    """
    stack: List[ast.stmt] = list(stmts)
    while stack:
        node = stack.pop()

        if isinstance(node, ast.Import):
            for alias in node.names:
                names_set.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names_set.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names_set.add(node.name)
            continue  # these DO open a new scope -- do not descend into their body
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                _collect_target_names(t, names_set)
        elif isinstance(node, ast.AnnAssign):
            _collect_target_names(node.target, names_set)
        elif isinstance(node, ast.AugAssign):
            _collect_target_names(node.target, names_set)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names_set.add(node.name)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _collect_target_names(node.target, names_set)
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars:
                    _collect_target_names(item.optional_vars, names_set)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                stack.append(child)


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
    quality_score: float   # 0.0 to 100.0, clamped
    # The same score before clamping. Two files at quality_score 0.0 are not
    # equally bad -- one may be -12 and the other -900 -- and callers that
    # rank candidates (ttc_solver) need to tell them apart.
    raw_score: float = 100.0
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

    # The SOV-001 "sovereign brand hygiene" rule was removed entirely. See the
    # module docstring: it matched the bare words "hermes", "claude" and
    # "kimi" anywhere in a file and raised a CRITICAL that failed the file.
    #
    # "hermes" and "kimi" appear nowhere else in this repository -- the list
    # was carried in from some other project. And a model id is not a defect:
    # you cannot call a model without naming it. Quality checks are for
    # correctness and safety; what a string says is not either.

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def _calculate_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Computes maximum AST control block nesting depth without descending into nested functions."""
        nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
        match_type = getattr(ast, "Match", None)
        if match_type:
            nesting_types = nesting_types + (match_type,)

        max_depth = current_depth

        for child in ast.iter_child_nodes(node):
            # Do NOT descend into nested function or class definitions
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, nesting_types):
                sub_depth = self._calculate_nesting_depth(child, current_depth + 1)
            else:
                sub_depth = self._calculate_nesting_depth(child, current_depth)
            if sub_depth > max_depth:
                max_depth = sub_depth

        return max_depth

    def _detect_undefined_names(self, tree: ast.AST) -> List[QualityIssue]:
        """Detects references to undefined names and missing imports using AST scope analysis."""
        issues: List[QualityIssue] = []

        tree_body: List[ast.stmt] = getattr(tree, "body", [])
        has_wildcard = any(
            isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
            for n in tree_body
        )
        if has_wildcard:
            return issues

        global_names: Set[str] = set(_BUILTIN_NAMES)
        _collect_module_level_bindings(tree_body, global_names)

        class ScopeVisitor(ast.NodeVisitor):
            def __init__(self, globals_set: Set[str]):
                self.scopes: List[Set[str]] = [set(globals_set)]

            def _is_defined(self, name: str) -> bool:
                return any(name in s for s in self.scopes)

            def _collect_local_bindings(self, stmts: Sequence[ast.AST]) -> Set[str]:
                """Collects variable bindings in the current scope without descending into child scopes."""
                bindings: Set[str] = set()
                stack: List[ast.AST] = list(stmts)
                while stack:
                    curr = stack.pop()
                    # Boundary: do NOT descend into nested function, class, or comprehension scopes
                    if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        bindings.add(curr.name)
                        continue
                    if isinstance(curr, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)):
                        continue

                    if isinstance(curr, ast.Name) and isinstance(curr.ctx, ast.Store):
                        bindings.add(curr.id)
                    elif isinstance(curr, ast.ExceptHandler) and curr.name:
                        bindings.add(curr.name)
                    elif isinstance(curr, ast.Import):
                        for alias in curr.names:
                            bindings.add(alias.asname or alias.name.split(".")[0])
                    elif isinstance(curr, ast.ImportFrom):
                        for alias in curr.names:
                            if alias.name != "*":
                                bindings.add(alias.asname or alias.name)

                    stack.extend(ast.iter_child_nodes(curr))
                return bindings

            def _process_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
                for d in node.decorator_list:
                    self.visit(d)
                if node.returns:
                    self.visit(node.returns)
                for d in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                    self.visit(d)

                local_scope: Set[str] = set()
                posonly = getattr(node.args, "posonlyargs", [])
                for arg in posonly + node.args.args + node.args.kwonlyargs:
                    local_scope.add(arg.arg)
                    if arg.annotation:
                        self.visit(arg.annotation)
                if node.args.vararg:
                    local_scope.add(node.args.vararg.arg)
                    if node.args.vararg.annotation:
                        self.visit(node.args.vararg.annotation)
                if node.args.kwarg:
                    local_scope.add(node.args.kwarg.arg)
                    if node.args.kwarg.annotation:
                        self.visit(node.args.kwarg.annotation)

                # Collect bindings without leaking inner function definitions into local scope
                local_scope |= self._collect_local_bindings(node.body)

                self.scopes.append(local_scope)
                for stmt in node.body:
                    self.visit(stmt)
                self.scopes.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._process_function(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._process_function(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                for base in node.bases:
                    self.visit(base)
                for d in node.decorator_list:
                    self.visit(d)

                class_scope = self._collect_local_bindings(node.body)
                self.scopes.append(class_scope)
                for stmt in node.body:
                    self.visit(stmt)
                self.scopes.pop()

            def _visit_comprehension(self, node: Union[ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp]) -> None:
                comp_scope: Set[str] = set()
                for gen in node.generators:
                    self.visit(gen.iter)
                    for n in ast.walk(gen.target):
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                            comp_scope.add(n.id)

                self.scopes.append(comp_scope)
                for gen in node.generators:
                    for if_expr in gen.ifs:
                        self.visit(if_expr)
                if isinstance(node, ast.DictComp):
                    self.visit(node.key)
                    self.visit(node.value)
                else:
                    self.visit(node.elt)
                self.scopes.pop()

            def visit_ListComp(self, node: ast.ListComp) -> None:
                self._visit_comprehension(node)

            def visit_SetComp(self, node: ast.SetComp) -> None:
                self._visit_comprehension(node)

            def visit_DictComp(self, node: ast.DictComp) -> None:
                self._visit_comprehension(node)

            def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
                self._visit_comprehension(node)

            def visit_Lambda(self, node: ast.Lambda) -> None:
                """Lambda parameters are their own scope, same as a function's."""
                for d in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                    self.visit(d)

                local_scope: Set[str] = set()
                posonly = getattr(node.args, "posonlyargs", [])
                for arg in posonly + node.args.args + node.args.kwonlyargs:
                    local_scope.add(arg.arg)
                if node.args.vararg:
                    local_scope.add(node.args.vararg.arg)
                if node.args.kwarg:
                    local_scope.add(node.args.kwarg.arg)

                self.scopes.append(local_scope)
                self.visit(node.body)
                self.scopes.pop()

            def visit_Name(self, node: ast.Name) -> None:
                if isinstance(node.ctx, ast.Load):
                    if not self._is_defined(node.id):
                        issues.append(QualityIssue(
                            severity="CRITICAL",
                            rule_id="UNDEF-001",
                            message=f"Undefined name '{node.id}': missing import or variable definition.",
                            line_number=node.lineno,
                            column=node.col_offset,
                        ))

        ScopeVisitor(global_names).visit(tree)
        return issues

    def check_code(self, code: str, file_path: Optional[str] = None) -> QualityReport:
        """Performs static AST inspection, type coverage evaluation, and hygiene checks."""
        issues: List[QualityIssue] = []
        score = 100.0

        # 1. Syntax and AST Parse Check
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

        # 2. Undefined Name & Missing Import Check (UNDEF-001)
        undef_issues = self._detect_undefined_names(tree)
        for issue in undef_issues:
            issues.append(issue)
            score -= 25.0

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
                # Check parameters (excluding 'self' and 'cls') across all 5 parameter groups
                all_params: List[ast.arg] = []
                posonly = getattr(args, "posonlyargs", [])
                for a in posonly:
                    if a.arg not in ("self", "cls"):
                        all_params.append(a)
                for a in args.args:
                    if a.arg not in ("self", "cls"):
                        all_params.append(a)
                if args.vararg:
                    all_params.append(args.vararg)
                for a in args.kwonlyargs:
                    all_params.append(a)
                if args.kwarg:
                    all_params.append(args.kwarg)

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

        type_coverage = round((typed_functions / total_functions) * 100, 1) if total_functions > 0 else 0.0
        final_score = max(0.0, min(100.0, round(score, 1)))
        passed = final_score >= 70.0 and not any(i.severity == "CRITICAL" for i in issues)

        return QualityReport(
            passed=passed,
            quality_score=final_score,
            raw_score=round(score, 1),
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
        """
        Scan the workspace and return a scorecard.

        This stops at `max_files`, so on any real tree it reports a **sample**,
        not the workspace. The old return said `total_files_analyzed` and
        `all_passed` with nothing marking it partial -- so "all_passed: True"
        over the first 50 files `os.walk` happened to reach read as a clean
        bill of health for the whole repo. The result now carries
        `files_found`, `truncated` and `scan_is_complete`, and the pass key is
        named for what it covers.
        """
        candidates: List[str] = []
        ignored_names = {
            ".git", "node_modules", ".venv", ".venv_train", "build", "dist",
            "__pycache__", ".pytest_cache", ".saleha", ".turbo",
        }
        for root, dirs, files in os.walk(root_dir):
            # Prune ignored directories in-place so os.walk does not descend into them
            dirs[:] = [d for d in dirs if d not in ignored_names and not d.startswith(".")]
            for f in files:
                if f.endswith(".py") and not f.startswith("test_"):
                    candidates.append(os.path.join(root, f))

        # Sort so the sample is at least deterministic; os.walk order is not.
        candidates.sort()
        scanned = candidates[:max_files]
        reports = [self.check_file(path) for path in scanned]

        total_files = len(reports)
        truncated = len(candidates) > total_files
        avg_score = round(sum(r.quality_score for r in reports) / total_files, 1) if total_files > 0 else 100.0
        total_critical = sum(r.critical_count for r in reports)
        total_major = sum(r.major_count for r in reports)
        avg_type_coverage = round(sum(r.type_coverage_pct for r in reports) / total_files, 1) if total_files > 0 else 100.0

        return {
            "files_found": len(candidates),
            "files_analyzed": total_files,
            "truncated": truncated,
            "scan_is_complete": not truncated,
            "average_quality_score": avg_score,
            "total_critical_issues": total_critical,
            "total_major_issues": total_major,
            "average_type_coverage_pct": avg_type_coverage,
            "all_analyzed_passed": all(r.passed for r in reports),
            "note": (f"sample only: {total_files} of {len(candidates)} files"
                     if truncated else f"complete: all {total_files} files"),
        }


# Global instance
quality_guard = QualityGuard()
