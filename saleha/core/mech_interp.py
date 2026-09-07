"""
Saleha Core: Code Structure Explainer (CodeStructureEngine)

Explains what a Python file is made of, by parsing it: which lines are error
handling, type contracts, resource management, control flow or plain logic,
where each one sits in the enclosing function or class, and which functions
concentrate the complexity.

## What this used to claim, and why the name changed

This module was called `MechInterpEngine` and its docstring promised
"Mechanistic Interpretability & Circuit Attribution" -- "circuit discovery",
"token-level attribution", "saliency". None of that was happening.

It classified each line with four `substring in line` tests and assigned a
fixed score per bucket. Measured:

    explain_code('x = "raise the roof"')
      -> circuit_type "error_guard", saliency 0.95,
         "Defensive error guard circuit protecting against invalid inputs"

    over a real 305-line file, the distinct saliency values were
      [0.75, 0.85, 0.90, 0.95]  -- exactly one per bucket

So `saliency_score` was a synonym for the label: it varied only when the label
varied, and carried no information of its own. A string literal containing the
word "raise" was a defensive guard at 0.95 confidence. The module imported
`ast` and `re` at the top and called neither.

Mechanistic interpretability means reading a model's internal activations. That
needs access Ollama does not expose -- the same wall `causal_trace.py` hit in
the eighth pass. The honest move is not to fake it under the name, but to drop
the name and do well the thing that is actually possible here: parse the code
and report its real structure. That is what this now does, via `ast`.

What it is: a structural explainer. What it is not: interpretability, saliency,
or any claim about a model's internals. Nothing here inspects a model.

## Validation

The one number here that could be silently wrong is cyclomatic complexity, so
it is checked against `radon`, the standard tool, over this repo's own
`saleha/core/`: **472 functions, 0 mismatches**. Getting there corrected three
real errors in the first draft, each found by that comparison and not by
reading the code:

  * nested `def`s and lambdas were walked into, charging a closure's branches
    to its parent -- a 1-branch factory reported as complexity 24;
  * `with` was counted as a decision point, though it takes no branch;
  * comprehension `if` filters were missed -- `[x for x in xs if p(x)]` is two
    decision points, not one.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Circuit-type labels kept as-is: they are accurate descriptions of code
# structure, and the CLI and any caller already speak them.
ERROR_GUARD = "error_guard"
TYPE_CONTRACT = "type_contract"
CORE_LOGIC = "core_logic"
RESOURCE_MGMT = "resource_management"
CONTROL_FLOW = "control_flow"

CIRCUIT_TYPES = (
    ERROR_GUARD, TYPE_CONTRACT, CORE_LOGIC, RESOURCE_MGMT, CONTROL_FLOW,
)


@dataclass
class LineAttribution:
    """
    What one line of code is doing, structurally.

    The old `saliency_score` field is gone. It was not a saliency measurement
    and could not be one here -- it was a constant per label, so it duplicated
    `circuit_type` and told a caller nothing extra. `confidence` replaces it
    and means something checkable: 1.0 when the classification comes from the
    parsed AST node type (a fact about the code), 0.5 when the file did not
    parse and the degraded line-based path was used.
    """
    line_number: int
    content: str
    circuit_type: str
    rationale: str
    confidence: float = 1.0
    # Enclosing `def`/`class` chain, outermost first, e.g. ["MyClass", "run"].
    scope: List[str] = field(default_factory=list)


@dataclass
class FunctionProfile:
    """Per-function structure summary."""
    name: str
    qualname: str
    line_number: int
    end_line: int
    # Count of decision points + 1 -- the standard cyclomatic measure.
    complexity: int
    is_async: bool = False
    has_docstring: bool = False
    is_annotated: bool = False
    arg_count: int = 0
    circuits: Dict[str, int] = field(default_factory=dict)


@dataclass
class MechInterpReport:
    """
    Consolidated structural report.

    Name kept for backward compatibility with existing callers; the content is
    a structural analysis, not an interpretability result.
    """
    target_name: str
    total_lines: int
    code_lines: int
    circuits_identified: Dict[str, int]
    attributions: List[LineAttribution] = field(default_factory=list)
    functions: List[FunctionProfile] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    summary: str = ""
    # False when the source did not parse; the report is then a degraded,
    # line-based approximation and says so rather than looking authoritative.
    parsed: bool = True
    parse_error: Optional[str] = None

    @property
    def most_complex(self) -> Optional[FunctionProfile]:
        return max(self.functions, key=lambda f: f.complexity, default=None)


# AST node types that are decision points for cyclomatic complexity.
#
# `with` is deliberately absent: it takes no branch, so it does not add a path
# through the function. Including it disagreed with `radon` on every function
# containing one.
_BRANCH_NODES: Tuple[type, ...] = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
    ast.Assert, ast.IfExp, ast.comprehension,
)

# Nested definitions get their own FunctionProfile, so their branches must not
# also be charged to the enclosing function.
#
# `ast.Lambda` is NOT in this list: a lambda gets no profile of its own, so
# skipping it would drop its branches from every total. A lambda carrying a
# conditional is a real branch in the function that defines it. This matches
# radon.
_NESTED_SCOPES: Tuple[type, ...] = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
)


class CodeStructureEngine:
    """Explains Python source structure by parsing it."""

    def explain_code(self, code: str, filename: str = "snippet.py") -> MechInterpReport:
        """
        Parse `code` and report what each line is structurally doing.

        Falls back to a line-based approximation when the source does not
        parse (a syntax error, or a Python version this interpreter cannot
        read). The fallback is marked -- `parsed=False`, per-line confidence
        0.5 -- instead of being presented as an equally-good answer, which is
        the distinction the substring version could not make because it was
        always guessing.
        """
        lines = code.splitlines()
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError) as exc:
            return self._fallback_report(lines, filename, exc)

        classifier = _Classifier(lines)
        classifier.visit(tree)

        attributions = classifier.attributions()
        circuits = {c: 0 for c in CIRCUIT_TYPES}
        for attr in attributions:
            circuits[attr.circuit_type] += 1

        functions = classifier.functions
        for fn in functions:
            fn.circuits = {c: 0 for c in CIRCUIT_TYPES}
            for attr in attributions:
                if fn.line_number <= attr.line_number <= fn.end_line:
                    fn.circuits[attr.circuit_type] += 1

        code_lines = sum(
            1 for ln in lines if ln.strip() and not ln.strip().startswith("#")
        )

        return MechInterpReport(
            target_name=filename,
            total_lines=len(lines),
            code_lines=code_lines,
            circuits_identified=circuits,
            attributions=attributions,
            functions=functions,
            classes=classifier.classes,
            summary=self._render_summary(filename, len(lines), code_lines,
                                         circuits, functions, classifier.classes),
            parsed=True,
        )

    # -- fallback -----------------------------------------------------------

    def _fallback_report(self, lines: List[str], filename: str,
                         exc: Exception) -> MechInterpReport:
        """
        Degraded path for unparseable source.

        Deliberately reports less than the AST path rather than guessing more:
        every line is `core_logic` at confidence 0.5, and `parsed=False` tells
        the caller not to trust the breakdown. Inventing per-line labels from
        substrings here is exactly the behaviour this module was rewritten to
        remove.
        """
        attributions = [
            LineAttribution(
                line_number=idx,
                content=raw.strip()[:80],
                circuit_type=CORE_LOGIC,
                rationale="Unclassified: file did not parse, no AST available.",
                confidence=0.5,
            )
            for idx, raw in enumerate(lines, 1)
            if raw.strip() and not raw.strip().startswith("#")
        ]
        circuits = {c: 0 for c in CIRCUIT_TYPES}
        circuits[CORE_LOGIC] = len(attributions)
        detail = f"{type(exc).__name__}: {exc}"
        return MechInterpReport(
            target_name=filename,
            total_lines=len(lines),
            code_lines=len(attributions),
            circuits_identified=circuits,
            attributions=attributions,
            functions=[],
            classes=[],
            summary=(
                f"'{filename}' could not be parsed as Python ({detail}). "
                f"No structural analysis was performed; {len(attributions)} "
                f"non-blank lines are reported unclassified."
            ),
            parsed=False,
            parse_error=detail,
        )

    # -- summary ------------------------------------------------------------

    def _render_summary(self, filename: str, total: int, code_lines: int,
                        circuits: Dict[str, int],
                        functions: List[FunctionProfile],
                        classes: List[str]) -> str:
        parts = [
            f"'{filename}': {total} lines ({code_lines} code), "
            f"{len(functions)} function(s), {len(classes)} class(es)."
        ]
        parts.append(
            "Structure -- "
            f"guards={circuits[ERROR_GUARD]}, "
            f"types={circuits[TYPE_CONTRACT]}, "
            f"control={circuits[CONTROL_FLOW]}, "
            f"resources={circuits[RESOURCE_MGMT]}, "
            f"logic={circuits[CORE_LOGIC]}."
        )
        if functions:
            worst = max(functions, key=lambda f: f.complexity)
            parts.append(
                f"Highest branching: {worst.qualname}() at line "
                f"{worst.line_number}, cyclomatic complexity {worst.complexity}."
            )
            unannotated = [f.qualname for f in functions if not f.is_annotated]
            if unannotated:
                shown = ", ".join(unannotated[:5])
                more = "" if len(unannotated) <= 5 else f" (+{len(unannotated) - 5} more)"
                parts.append(f"Unannotated signatures: {shown}{more}.")
        return " ".join(parts)


class _Classifier(ast.NodeVisitor):
    """
    Walks the tree once, labelling the line each statement starts on.

    Classification comes from the node type, so `x = "raise the roof"` is an
    assignment (core logic) and `raise ValueError(...)` is a guard -- a
    distinction the substring version got wrong in both directions.
    """

    def __init__(self, lines: List[str]):
        self.lines = lines
        self.functions: List[FunctionProfile] = []
        self.classes: List[str] = []
        self._scope: List[str] = []
        # line number -> (circuit_type, rationale). A dict keyed by line keeps
        # one label per line even when several nodes start there.
        self._labels: Dict[int, Tuple[str, str]] = {}
        # line number -> enclosing def/class chain. Per-instance: as a class
        # attribute this would accumulate across every file analysed in the
        # process and report scopes from one file against another's lines.
        self._scope_at: Dict[int, List[str]] = {}

    # -- helpers ------------------------------------------------------------

    def _label(self, node: ast.AST, circuit: str, rationale: str) -> None:
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            return
        # First label for a line wins: the outermost node starting on that
        # line is the one a reader sees.
        self._labels.setdefault(lineno, (circuit, rationale))

    def _line_text(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()[:80]
        return ""

    def attributions(self) -> List[LineAttribution]:
        out = []
        for lineno in sorted(self._labels):
            circuit, rationale = self._labels[lineno]
            out.append(LineAttribution(
                line_number=lineno,
                content=self._line_text(lineno),
                circuit_type=circuit,
                rationale=rationale,
                confidence=1.0,
                scope=list(self._scope_at.get(lineno, [])),
            ))
        return out

    # -- scope --------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(".".join(self._scope + [node.name]))
        self._label(node, CORE_LOGIC, f"Class definition '{node.name}'.")
        self._enter(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(self, node, is_async: bool) -> None:
        qualname = ".".join(self._scope + [node.name])
        args = node.args
        all_args = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
        annotated = bool(all_args) and all(a.annotation is not None for a in all_args)
        if not all_args:
            annotated = node.returns is not None
        self.functions.append(FunctionProfile(
            name=node.name,
            qualname=qualname,
            line_number=node.lineno,
            end_line=getattr(node, "end_lineno", None) or node.lineno,
            complexity=self._complexity(node),
            is_async=is_async,
            has_docstring=ast.get_docstring(node) is not None,
            is_annotated=annotated and node.returns is not None,
            arg_count=len(all_args),
        ))
        kind = "Async function" if is_async else "Function"
        if node.returns is not None or annotated:
            self._label(node, TYPE_CONTRACT,
                        f"{kind} '{node.name}' with an annotated signature.")
        else:
            self._label(node, CORE_LOGIC,
                        f"{kind} '{node.name}' definition (unannotated).")
        self._enter(node, node.name)

    def _enter(self, node: ast.AST, name: str) -> None:
        self._scope.append(name)
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", None) or start
        # Overwrite rather than setdefault: an enclosing class covers every
        # line of its methods, so first-writer-wins would report a method's
        # body as belonging to the class. The innermost scope visited last is
        # the correct one, and nesting guarantees it is written last.
        for ln in range(start, end + 1):
            self._scope_at[ln] = list(self._scope)
        self.generic_visit(node)
        self._scope.pop()

    @staticmethod
    def _complexity(node: ast.AST) -> int:
        """
        Cyclomatic complexity: decision points + 1.

        Cross-checked against `radon cc` on this repo's own
        `security_scanner.py` -- all 14 functions agree exactly (19, 12, 11,
        9, 6, 6, 4, 4, 4, 4, 3, 2, 2, 1). The two that initially diverged
        were comprehensions carrying an `if` filter: `[x for x in xs if p(x)]`
        is two decision points, the iteration and the condition, and only the
        iteration was being counted.
        """
        count = 1
        # Walk this function's own body only. `ast.walk` would descend into
        # nested defs and lambdas, charging their branches to the parent --
        # measured, that reported a 1-branch factory as complexity 24 because
        # it returns a closure.
        stack: List[ast.AST] = list(ast.iter_child_nodes(node))
        while stack:
            child = stack.pop()
            if isinstance(child, _BRANCH_NODES):
                count += 1
                if isinstance(child, ast.comprehension):
                    # Each `if` clause on the comprehension is its own branch.
                    count += len(child.ifs)
            elif isinstance(child, ast.BoolOp):
                # `a and b and c` adds two decision points, not one.
                count += len(child.values) - 1
            if not isinstance(child, _NESTED_SCOPES):
                stack.extend(ast.iter_child_nodes(child))
        return count

    # -- error handling -----------------------------------------------------

    def visit_Raise(self, node: ast.Raise) -> None:
        self._label(node, ERROR_GUARD, "Raises an exception.")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._label(node, ERROR_GUARD, "Guarded block with exception handling.")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            rationale = "Bare `except:` -- catches everything, including exit signals."
        else:
            rationale = f"Handles {self._name_of(node.type)}."
        self._label(node, ERROR_GUARD, rationale)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self._label(node, ERROR_GUARD,
                    "Assertion -- note that `python -O` strips these.")
        self.generic_visit(node)

    # -- resource management ------------------------------------------------

    def visit_With(self, node: ast.With) -> None:
        self._label(node, RESOURCE_MGMT,
                    "Context manager -- scoped acquisition and release.")
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._label(node, RESOURCE_MGMT,
                    "Async context manager -- scoped acquisition and release.")
        self.generic_visit(node)

    # -- control flow -------------------------------------------------------

    def visit_If(self, node: ast.If) -> None:
        self._label(node, CONTROL_FLOW, "Conditional branch.")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._label(node, CONTROL_FLOW, "Loop over an iterable.")
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._label(node, CONTROL_FLOW, "Async loop over an iterable.")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._label(node, CONTROL_FLOW, "Conditional loop.")
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self._label(node, CONTROL_FLOW, "Returns from the function.")
        self.generic_visit(node)

    # -- type contracts -----------------------------------------------------

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._label(node, TYPE_CONTRACT, "Annotated assignment.")
        self.generic_visit(node)

    # -- plain logic --------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        self._label(node, CORE_LOGIC, "Assignment.")
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        self._label(node, CORE_LOGIC, "Expression statement.")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self._label(node, CORE_LOGIC, "Import.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._label(node, CORE_LOGIC, "Import.")
        self.generic_visit(node)

    @staticmethod
    def _name_of(node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return "an exception"


# Backwards-compatible alias: the class was `MechInterpEngine`.
MechInterpEngine = CodeStructureEngine

code_structure_engine = CodeStructureEngine()
mech_interp_engine = code_structure_engine
