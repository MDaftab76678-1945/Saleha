"""Saleha Tools: AST Inspector & Static Analysis Engine.

Production-grade, single-pass AST static analysis framework for Python.
Performs comprehensive structural inspection, isolated cyclomatic complexity
(McCabe), cognitive complexity (SonarQube standard), Halstead software science
metrics, full 5-tier parameter type coverage, security lints (Bandit-lite),
and maintainability index calculation without executing any user code.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
import enum
import math
import os
import re
import sys
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, Union

from saleha.tools.base import BaseTool, ToolResult


# =====================================================================
# Section 1: Domain Enums & Classification Constants
# =====================================================================

class ScopeKind(str, enum.Enum):
    """Enumeration of lexical scope types within Python AST."""
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    LAMBDA = "lambda"
    COMPREHENSION = "comprehension"


class IssueSeverity(str, enum.Enum):
    """Severity classification for static analysis findings."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ArgumentKind(str, enum.Enum):
    """Python argument passing conventions (Python 3.8+ specification)."""
    POSITIONAL_ONLY = "posonly"
    POSITIONAL_OR_KEYWORD = "pos_or_kw"
    VAR_POSITIONAL = "vararg"  # *args
    KEYWORD_ONLY = "kwonly"
    VAR_KEYWORD = "kwarg"  # **kwargs


class MaintainabilityGrade(str, enum.Enum):
    """Software Engineering Institute (SEI) Maintainability Grades."""
    A = "A"  # High Maintainability (>= 65)
    B = "B"  # Moderate Maintainability (40 - 64)
    C = "C"  # Low Maintainability / High Technical Debt (< 40)


# Known hazardous symbols and functions for static security checks
HAZARDOUS_CALLS: FrozenSet[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
})

INSECURE_DESERIALIZERS: FrozenSet[Tuple[str, str]] = frozenset({
    ("pickle", "loads"),
    ("pickle", "load"),
    ("_pickle", "loads"),
    ("_pickle", "load"),
    ("marshal", "loads"),
    ("marshal", "load"),
    ("shelve", "open"),
})

SUSPICIOUS_VARIABLE_NAMES: FrozenSet[str] = frozenset({
    "api_key",
    "apikey",
    "secret",
    "secret_key",
    "password",
    "passwd",
    "auth_token",
    "access_token",
    "private_key",
})


# =====================================================================
# Section 2: Data Models & Container Classes
# =====================================================================

@dataclass
class ArgumentDetail:
    """Detailed structural information for a single function parameter."""
    name: str
    kind: ArgumentKind
    has_annotation: bool
    annotation: Optional[str] = None
    has_default: bool = False
    default_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts argument detail to a plain dictionary."""
        return {
            "name": self.name,
            "kind": self.kind.value,
            "has_annotation": self.has_annotation,
            "annotation": self.annotation,
            "has_default": self.has_default,
            "default_value": self.default_value,
        }


@dataclass
class FunctionMetrics:
    """Structural, complexity, and type metrics for a function or method."""
    name: str
    lineno: int
    end_lineno: int
    is_async: bool
    is_generator: bool
    is_method: bool
    parent_class: Optional[str]
    docstring: str
    arguments: List[ArgumentDetail]
    total_args_count: int
    typed_args_count: int
    has_return_type: bool
    return_type: Optional[str]
    cyclomatic_complexity: int
    cognitive_complexity: int
    lines_of_code: int
    decorators: List[str] = field(default_factory=list)
    calls_made: List[str] = field(default_factory=list)

    @property
    def is_fully_typed(self) -> bool:
        """Determines if the function has 100% typed arguments and return type."""
        args_typed = (self.typed_args_count == self.total_args_count)
        return args_typed and self.has_return_type

    def to_dict(self) -> Dict[str, Any]:
        """Serializes function metrics to standard dictionary."""
        return {
            "name": self.name,
            "line_number": self.lineno,
            "end_line_number": self.end_lineno,
            "is_async": self.is_async,
            "is_generator": self.is_generator,
            "is_method": self.is_method,
            "parent_class": self.parent_class,
            "docstring": self.docstring,
            "total_args_count": self.total_args_count,
            "typed_args_count": self.typed_args_count,
            "has_return_type": self.has_return_type,
            "return_type": self.return_type,
            "is_fully_typed": self.is_fully_typed,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "cognitive_complexity": self.cognitive_complexity,
            "lines_of_code": self.lines_of_code,
            "decorators": self.decorators,
            "calls_made": self.calls_made,
            "arguments": [a.to_dict() for a in self.arguments],
        }


@dataclass
class ClassMetrics:
    """Structural metadata for a class definition."""
    name: str
    lineno: int
    end_lineno: int
    docstring: str
    bases: List[str]
    decorators: List[str]
    methods: List[str]
    method_count: int
    class_variables: List[str]
    inner_classes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes class metrics to standard dictionary."""
        return {
            "name": self.name,
            "line_number": self.lineno,
            "end_line_number": self.end_lineno,
            "docstring": self.docstring,
            "bases": self.bases,
            "decorators": self.decorators,
            "methods": self.methods,
            "method_count": self.method_count,
            "class_variables": self.class_variables,
            "inner_classes": self.inner_classes,
        }


@dataclass
class ImportDetail:
    """Structural information for an import statement."""
    module: str
    name: Optional[str]
    alias: Optional[str]
    lineno: int
    is_from_import: bool
    is_wildcard: bool
    is_type_guard: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes import detail to standard dictionary."""
        return {
            "module": self.module,
            "name": self.name,
            "alias": self.alias,
            "line_number": self.lineno,
            "is_from_import": self.is_from_import,
            "is_wildcard": self.is_wildcard,
            "is_type_guard": self.is_type_guard,
        }


@dataclass
class SecurityFinding:
    """Security risk or dangerous pattern identified in AST."""
    rule_id: str
    severity: IssueSeverity
    message: str
    lineno: int
    col_offset: int
    code_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes finding to dictionary."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "line_number": self.lineno,
            "col_offset": self.col_offset,
            "code_snippet": self.code_snippet,
        }


@dataclass
class CodeSmell:
    """Maintainability issue or code smell identified in AST."""
    rule_id: str
    message: str
    lineno: int
    category: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes code smell to dictionary."""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "line_number": self.lineno,
            "category": self.category,
        }


@dataclass
class HalsteadMetrics:
    """Maurice Halstead's Software Science complexity metrics."""
    distinct_operators: int = 0
    total_operators: int = 0
    distinct_operands: int = 0
    total_operands: int = 0

    @property
    def vocabulary(self) -> int:
        """Program vocabulary: n = n1 + n2."""
        return self.distinct_operators + self.distinct_operands

    @property
    def length(self) -> int:
        """Program total length: N = N1 + N2."""
        return self.total_operators + self.total_operands

    @property
    def calculated_length(self) -> float:
        """Estimated length: N^ = n1 * log2(n1) + n2 * log2(n2)."""
        n1 = self.distinct_operators
        n2 = self.distinct_operands
        term1 = (n1 * math.log2(n1)) if n1 > 0 else 0.0
        term2 = (n2 * math.log2(n2)) if n2 > 0 else 0.0
        return round(term1 + term2, 2)

    @property
    def volume(self) -> float:
        """Halstead volume: V = N * log2(n)."""
        if self.vocabulary <= 0:
            return 0.0
        return round(self.length * math.log2(self.vocabulary), 2)

    @property
    def difficulty(self) -> float:
        """Program difficulty: D = (n1 / 2) * (N2 / n2)."""
        if self.distinct_operands <= 0 or self.distinct_operators <= 0:
            return 0.0
        return round((self.distinct_operators / 2.0) * (self.total_operands / self.distinct_operands), 2)

    @property
    def effort(self) -> float:
        """Mental effort: E = D * V."""
        return round(self.difficulty * self.volume, 2)

    @property
    def time_seconds(self) -> float:
        """Estimated implementation time: T = E / 18 seconds."""
        return round(self.effort / 18.0, 2)

    @property
    def delivered_bugs(self) -> float:
        """Estimated delivered defects: B = V / 3000."""
        return round(self.volume / 3000.0, 4)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes Halstead metrics to dictionary."""
        return {
            "distinct_operators": self.distinct_operators,
            "total_operators": self.total_operators,
            "distinct_operands": self.distinct_operands,
            "total_operands": self.total_operands,
            "vocabulary": self.vocabulary,
            "length": self.length,
            "calculated_length": self.calculated_length,
            "volume": self.volume,
            "difficulty": self.difficulty,
            "effort": self.effort,
            "time_seconds": self.time_seconds,
            "delivered_bugs": self.delivered_bugs,
        }


# =====================================================================
# Section 3: Isolated Complexity Calculators (McCabe & Cognitive)
# =====================================================================

class IsolatedMcCabeCalculator:
    """Computes McCabe Cyclomatic Complexity strictly isolated from nested scopes.

    Prevents scope bleed by stopping traversal at child function boundaries
    (`FunctionDef`, `AsyncFunctionDef`, and `Lambda`).
    Properly accounts for all Python control flow:
    - If, While, For, AsyncFor, ExceptHandler, With, AsyncWith, Assert
    - Ternary operators (IfExp)
    - List/Dict/Set/Generator comprehensions (loop + if filters)
    - Boolean operations (And/Or decision points)
    - Pattern matching case statements (Python 3.10+ match_case)
    """

    @classmethod
    def calculate(cls, root_node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda]) -> int:
        """Calculates cyclomatic complexity for a given function node."""
        complexity = 1  # Base linear execution path

        # Stack-based traversal to allow skipping nested subtrees
        stack: List[ast.AST] = list(ast.iter_child_nodes(root_node))

        while stack:
            current = stack.pop()

            # CRITICAL BOUNDARY: Do NOT descend into nested functions or async functions
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Check decision points
            if isinstance(current, (ast.If, ast.IfExp)):
                complexity += 1
            elif isinstance(current, (ast.For, ast.AsyncFor, ast.While)):
                complexity += 1
            elif isinstance(current, ast.ExceptHandler):
                complexity += 1
            elif isinstance(current, (ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(current, ast.Assert):
                complexity += 1
            elif isinstance(current, ast.BoolOp):
                # E.g. 'a and b and c' introduces len(values) - 1 decision points
                complexity += max(0, len(current.values) - 1)
            elif isinstance(current, ast.comprehension):
                # 1 for the comprehension iteration + 1 for each 'if' filter
                complexity += 1 + len(current.ifs)

            # Python 3.10+ match-case statement support
            match_case_type = getattr(ast, "match_case", None)
            if match_case_type and isinstance(current, match_case_type):
                complexity += 1

            # Push children of current node to stack
            stack.extend(ast.iter_child_nodes(current))

        return complexity


class CognitiveComplexityCalculator:
    """Computes Cognitive Complexity according to SonarQube specification.

    Unlike Cyclomatic Complexity (which measures testability), Cognitive Complexity
    measures readability and human comprehension difficulty.
    Rules:
    - Increments on control flow breaks: if, ternary, loops, except.
    - Adds a nesting penalty for control structures nested within other structures.
    - Increments on switches in boolean operators (e.g. 'a and b or c').
    - Increments on jump statements (break, continue).
    """

    @classmethod
    def calculate(cls, root_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> int:
        """Calculates cognitive complexity for a given function node."""
        visitor = _CognitiveComplexityVisitor()
        for child in ast.iter_child_nodes(root_node):
            visitor.visit(child)
        return visitor.total_complexity


class _CognitiveComplexityVisitor(ast.NodeVisitor):
    """Internal visitor that tracks nesting level and cognitive penalties."""

    def __init__(self) -> None:
        self.total_complexity: int = 0
        self.nesting_level: int = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Nested functions increase nesting level for their internal contents."""
        self.nesting_level += 1
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.nesting_level -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Nested async functions increase nesting level."""
        self.nesting_level += 1
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.nesting_level -= 1

    def visit_If(self, node: ast.If) -> None:
        """Increments complexity by 1 + nesting level for 'if' statements."""
        self.total_complexity += 1 + self.nesting_level
        self.nesting_level += 1
        for stmt in node.body:
            self.visit(stmt)
        self.nesting_level -= 1

        # Check 'else' / 'elif' branch
        if node.orelse:
            # If orelse contains a single 'If', it represents 'elif'
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # Elif gets +1 increment with NO nesting penalty
                self.total_complexity += 1
                for stmt in node.orelse[0].body:
                    self.visit(stmt)
                if node.orelse[0].orelse:
                    self._visit_orelse(node.orelse[0].orelse)
            else:
                # Regular 'else' gets +1 with NO nesting penalty
                self.total_complexity += 1
                self._visit_orelse(node.orelse)

    def _visit_orelse(self, orelse_nodes: List[ast.stmt]) -> None:
        """Processes else block body."""
        self.nesting_level += 1
        for stmt in orelse_nodes:
            self.visit(stmt)
        self.nesting_level -= 1

    def visit_IfExp(self, node: ast.IfExp) -> None:
        """Ternary operator: adds 1 + nesting level."""
        self.total_complexity += 1 + self.nesting_level
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Loop: adds 1 + nesting level."""
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Async loop: adds 1 + nesting level."""
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        """While loop: adds 1 + nesting level."""
        self._visit_loop(node)

    def _visit_loop(self, node: Union[ast.For, ast.AsyncFor, ast.While]) -> None:
        self.total_complexity += 1 + self.nesting_level
        self.nesting_level += 1
        for stmt in node.body:
            self.visit(stmt)
        self.nesting_level -= 1
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Except handler: adds 1 + nesting level."""
        self.total_complexity += 1 + self.nesting_level
        self.nesting_level += 1
        for stmt in node.body:
            self.visit(stmt)
        self.nesting_level -= 1

    def visit_Break(self, node: ast.Break) -> None:
        """Break statement adds 1 without nesting penalty."""
        self.total_complexity += 1

    def visit_Continue(self, node: ast.Continue) -> None:
        """Continue statement adds 1 without nesting penalty."""
        self.total_complexity += 1


# =====================================================================
# Section 4: Halstead Software Science Collector
# =====================================================================

class HalsteadCollector(ast.NodeVisitor):
    """Gathers operators and operands across an AST in a single traversal."""

    OPERATOR_TYPES: FrozenSet[type] = frozenset({
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd, ast.MatMult,
        ast.And, ast.Or, ast.Not, ast.Invert, ast.UAdd, ast.USub,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
        ast.In, ast.NotIn,
    })

    def __init__(self) -> None:
        self.operators: List[str] = []
        self.operands: List[str] = []

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self.operators.append(type(node.op).__name__)
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        self.operators.append(type(node.op).__name__)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.operators.append(type(node.op).__name__)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            self.operators.append(type(op).__name__)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.operators.append("Assign")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.operators.append(f"Aug_{type(node.op).__name__}")
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.operators.append("Return")
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        self.operators.append("Yield")
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self.operators.append("YieldFrom")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.operators.append("Call")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Operands: constants
        val_repr = repr(node.value)
        self.operands.append(val_repr)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # Operands: variable identifiers
        self.operands.append(node.id)
        self.generic_visit(node)

    def build_metrics(self) -> HalsteadMetrics:
        """Constructs HalsteadMetrics from collected operators and operands."""
        distinct_ops = len(set(self.operators))
        total_ops = len(self.operators)
        distinct_opnds = len(set(self.operands))
        total_opnds = len(self.operands)

        return HalsteadMetrics(
            distinct_operators=distinct_ops,
            total_operators=total_ops,
            distinct_operands=distinct_opnds,
            total_operands=total_opnds,
        )


# =====================================================================
# Section 5: Single-Pass Master AST Visitor
# =====================================================================

class SinglePassASTVisitor(ast.NodeVisitor):
    """Comprehensive single-pass AST visitor for Python source analysis.

    Eliminates redundant tree walks (O(4N) -> O(N)) by extracting classes,
    functions, imports, parameters, security issues, and code smells in
    a single unified pass over the syntax tree.
    """

    def __init__(self, source_lines: List[str], file_path: Optional[str] = None) -> None:
        self.source_lines: List[str] = source_lines
        self.file_path: Optional[str] = file_path

        # Extracted models
        self.classes: List[ClassMetrics] = []
        self.functions: List[FunctionMetrics] = []
        self.imports: List[ImportDetail] = []
        self.security_findings: List[SecurityFinding] = []
        self.code_smells: List[CodeSmell] = []

        # Scope context tracking
        self.class_stack: List[str] = []
        self.current_function: Optional[str] = None
        self.in_type_checking_guard: bool = False

        # Call-graph tracking
        self.function_calls: Dict[str, List[str]] = {}

        # Halstead collector
        self.halstead_collector = HalsteadCollector()

        # Variable usage tracking for dead code detection
        self.function_assigned_vars: Dict[str, Set[str]] = {}
        self.function_referenced_vars: Dict[str, Set[str]] = {}

    def visit(self, node: ast.AST) -> None:
        """Visits a node and feeds the Halstead collector simultaneously."""
        self.halstead_collector.visit(node)
        super().visit(node)

    # -----------------------------------------------------------------
    # Import Handlers
    # -----------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        """Extracts standard 'import foo, bar as b' statements."""
        for alias in node.names:
            detail = ImportDetail(
                module=alias.name,
                name=None,
                alias=alias.asname,
                lineno=node.lineno,
                is_from_import=False,
                is_wildcard=False,
                is_type_guard=self.in_type_checking_guard,
            )
            self.imports.append(detail)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Extracts 'from foo import bar, *' statements."""
        mod = node.module or ""
        for alias in node.names:
            is_wildcard = (alias.name == "*")
            detail = ImportDetail(
                module=mod,
                name=alias.name,
                alias=alias.asname,
                lineno=node.lineno,
                is_from_import=True,
                is_wildcard=is_wildcard,
                is_type_guard=self.in_type_checking_guard,
            )
            self.imports.append(detail)

            # Security lint: SEC-007 (Wildcard import pollution)
            if is_wildcard:
                self.security_findings.append(SecurityFinding(
                    rule_id="SEC-007",
                    severity=IssueSeverity.WARNING,
                    message=f"Wildcard import 'from {mod} import *' pollutes namespace and obscures symbols.",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    code_snippet=self._get_snippet(node.lineno),
                ))

        self.generic_visit(node)

    # -----------------------------------------------------------------
    # Class Definition Handler
    # -----------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extracts class definition, base classes, decorators, and methods."""
        # Resolve base classes
        bases: List[str] = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    bases.append(f"{ast.unparse(b.value)}.{b.attr}")
            else:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    bases.append("<complex_base>")

        # Resolve decorators
        decorators: List[str] = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                decorators.append("<decorator>")

        # Immediate child methods and inner classes
        methods: List[str] = []
        class_variables: List[str] = []
        inner_classes: List[str] = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
            elif isinstance(item, ast.ClassDef):
                inner_classes.append(item.name)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                class_variables.append(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_variables.append(target.id)

        # Check duplicate methods
        seen_methods: Set[str] = set()
        for m in methods:
            if m in seen_methods:
                self.code_smells.append(CodeSmell(
                    rule_id="SMELL-006",
                    message=f"Duplicate method '{m}' defined in class '{node.name}'.",
                    lineno=node.lineno,
                    category="Duplication",
                ))
            seen_methods.add(m)

        docstring = (ast.get_docstring(node) or "").strip()
        end_lineno = getattr(node, "end_lineno", node.lineno)

        metrics = ClassMetrics(
            name=node.name,
            lineno=node.lineno,
            end_lineno=end_lineno,
            docstring=docstring,
            bases=bases,
            decorators=decorators,
            methods=methods,
            method_count=len(methods),
            class_variables=class_variables,
            inner_classes=inner_classes,
        )
        self.classes.append(metrics)

        # Push class stack for nested method tracking
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    # -----------------------------------------------------------------
    # Function Definition Handlers
    # -----------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extracts synchronous function and method metadata."""
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extracts asynchronous function and method metadata."""
        self._process_function(node, is_async=True)

    def _process_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        is_async: bool,
    ) -> None:
        """Common extraction logic for both sync and async functions."""
        # 1. Arguments Extraction (all 5 categories according to Python spec)
        args_details = self._extract_arguments(node)

        # Total args excluding self / cls
        total_args = len(args_details)
        typed_args = sum(1 for a in args_details if a.has_annotation)

        # 2. Return Type Annotation
        has_return = node.returns is not None
        return_type_str: Optional[str] = None
        if has_return and node.returns is not None:
            try:
                return_type_str = ast.unparse(node.returns)
            except Exception:
                return_type_str = "<annotation>"

        # 3. Isolated Cyclomatic Complexity (Zero nested scope bleed)
        cyclomatic = IsolatedMcCabeCalculator.calculate(node)

        # 4. Cognitive Complexity
        cognitive = CognitiveComplexityCalculator.calculate(node)

        # 5. Generator detection
        is_generator = any(
            isinstance(n, (ast.Yield, ast.YieldFrom))
            for n in ast.walk(node)
        )

        # 6. Decorators
        decorators: List[str] = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                decorators.append("<decorator>")

        # 7. Parent class context
        parent_class = self.class_stack[-1] if self.class_stack else None
        is_method = parent_class is not None

        # 8. Lines of code calculation
        end_lineno = getattr(node, "end_lineno", node.lineno)
        loc = max(1, end_lineno - node.lineno + 1)

        docstring = (ast.get_docstring(node) or "").strip()

        # Code Smells: Check excessive arguments
        if total_args > 6:
            self.code_smells.append(CodeSmell(
                rule_id="SMELL-001",
                message=f"Function '{node.name}' has {total_args} arguments (recommended <= 6).",
                lineno=node.lineno,
                category="Complexity",
            ))

        # Code Smells: Check long function
        if loc > 60:
            self.code_smells.append(CodeSmell(
                rule_id="SMELL-002",
                message=f"Function '{node.name}' is {loc} lines long (recommended <= 60).",
                lineno=node.lineno,
                category="Maintainability",
            ))

        # Code Smells: Check high cyclomatic complexity
        if cyclomatic > 10:
            self.code_smells.append(CodeSmell(
                rule_id="SMELL-003",
                message=f"Function '{node.name}' has high cyclomatic complexity ({cyclomatic}). Refactoring advised.",
                lineno=node.lineno,
                category="Complexity",
            ))

        # Build metric
        func_key = f"{parent_class}.{node.name}" if parent_class else node.name
        self.function_calls[func_key] = []
        self.function_assigned_vars[func_key] = set()
        self.function_referenced_vars[func_key] = set()

        # Enter function scope
        prev_func = self.current_function
        self.current_function = func_key

        # Traverse function body
        for stmt in node.body:
            self.visit(stmt)

        # Check unused local variables in function scope
        assigned = self.function_assigned_vars[func_key]
        referenced = self.function_referenced_vars[func_key]
        unused = assigned - referenced
        for var in unused:
            if not var.startswith("_") and var not in ("self", "cls"):
                self.code_smells.append(CodeSmell(
                    rule_id="SMELL-005",
                    message=f"Local variable '{var}' in function '{node.name}' is assigned but never read.",
                    lineno=node.lineno,
                    category="DeadCode",
                ))

        # Construct final model
        metrics = FunctionMetrics(
            name=node.name,
            lineno=node.lineno,
            end_lineno=end_lineno,
            is_async=is_async,
            is_generator=is_generator,
            is_method=is_method,
            parent_class=parent_class,
            docstring=docstring,
            arguments=args_details,
            total_args_count=total_args,
            typed_args_count=typed_args,
            has_return_type=has_return,
            return_type=return_type_str,
            cyclomatic_complexity=cyclomatic,
            cognitive_complexity=cognitive,
            lines_of_code=loc,
            decorators=decorators,
            calls_made=self.function_calls[func_key],
        )
        self.functions.append(metrics)

        # Exit function scope
        self.current_function = prev_func

    def _extract_arguments(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    ) -> List[ArgumentDetail]:
        """Extracts complete 5-category argument list according to Python spec.

        Properly aggregates:
        1. Positional-only arguments (Python 3.8+)
        2. Regular positional / keyword arguments
        3. Variable positional arguments (*args)
        4. Keyword-only arguments
        5. Variable keyword arguments (**kwargs)
        Excludes implicit method parameters 'self' and 'cls'.
        """
        details: List[ArgumentDetail] = []
        args_node = node.args

        # 1. Positional-only arguments
        posonly = getattr(args_node, "posonlyargs", [])
        for arg in posonly:
            if arg.arg not in ("self", "cls"):
                has_ann = (arg.annotation is not None)
                ann_str = ast.unparse(arg.annotation) if has_ann and arg.annotation else None
                details.append(ArgumentDetail(
                    name=arg.arg,
                    kind=ArgumentKind.POSITIONAL_ONLY,
                    has_annotation=has_ann,
                    annotation=ann_str,
                ))

        # 2. Regular arguments
        for arg in args_node.args:
            if arg.arg not in ("self", "cls"):
                has_ann = (arg.annotation is not None)
                ann_str = ast.unparse(arg.annotation) if has_ann and arg.annotation else None
                details.append(ArgumentDetail(
                    name=arg.arg,
                    kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                    has_annotation=has_ann,
                    annotation=ann_str,
                ))

        # 3. Variable positional (*args)
        if args_node.vararg:
            varg = args_node.vararg
            has_ann = (varg.annotation is not None)
            ann_str = ast.unparse(varg.annotation) if has_ann and varg.annotation else None
            details.append(ArgumentDetail(
                name=f"*{varg.arg}",
                kind=ArgumentKind.VAR_POSITIONAL,
                has_annotation=has_ann,
                annotation=ann_str,
            ))

        # 4. Keyword-only arguments
        for arg in args_node.kwonlyargs:
            has_ann = (arg.annotation is not None)
            ann_str = ast.unparse(arg.annotation) if has_ann and arg.annotation else None
            details.append(ArgumentDetail(
                name=arg.arg,
                kind=ArgumentKind.KEYWORD_ONLY,
                has_annotation=has_ann,
                annotation=ann_str,
            ))

        # 5. Variable keyword (**kwargs)
        if args_node.kwarg:
            kw = args_node.kwarg
            has_ann = (kw.annotation is not None)
            ann_str = ast.unparse(kw.annotation) if has_ann and kw.annotation else None
            details.append(ArgumentDetail(
                name=f"**{kw.arg}",
                kind=ArgumentKind.VAR_KEYWORD,
                has_annotation=has_ann,
                annotation=ann_str,
            ))

        return details

    # -----------------------------------------------------------------
    # Call, Name & Security Handlers
    # -----------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        """Detects hazardous function calls and builds intra-file call graph."""
        callee_name: Optional[str] = None

        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
            # SEC-001: eval / exec / __import__
            if callee_name in HAZARDOUS_CALLS:
                self.security_findings.append(SecurityFinding(
                    rule_id="SEC-001",
                    severity=IssueSeverity.CRITICAL,
                    message=f"Insecure execution of dynamic code via '{callee_name}()'.",
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    code_snippet=self._get_snippet(node.lineno),
                ))

        elif isinstance(node.func, ast.Attribute):
            try:
                base_name = ast.unparse(node.func.value)
                attr_name = node.func.attr
                callee_name = f"{base_name}.{attr_name}"

                # SEC-002: subprocess.call/run/Popen with shell=True
                if base_name in ("subprocess", "os") and attr_name in ("Popen", "call", "run", "check_call", "check_output", "system"):
                    for kw in node.keywords:
                        if kw.arg == "shell":
                            is_shell_true = False
                            if isinstance(kw.value, ast.Constant) and bool(kw.value.value) is True:
                                is_shell_true = True
                            if is_shell_true:
                                self.security_findings.append(SecurityFinding(
                                    rule_id="SEC-002",
                                    severity=IssueSeverity.CRITICAL,
                                    message=f"Command injection risk: '{callee_name}' invoked with shell=True.",
                                    lineno=node.lineno,
                                    col_offset=node.col_offset,
                                    code_snippet=self._get_snippet(node.lineno),
                                ))

                # SEC-003: Insecure deserialization
                if (base_name, attr_name) in INSECURE_DESERIALIZERS:
                    self.security_findings.append(SecurityFinding(
                        rule_id="SEC-003",
                        severity=IssueSeverity.HIGH,
                        message=f"Arbitrary code execution risk: Insecure deserialization via '{callee_name}'.",
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        code_snippet=self._get_snippet(node.lineno),
                    ))

            except Exception:
                pass

        # Record call graph edge if inside function
        if self.current_function and callee_name:
            self.function_calls[self.current_function].append(callee_name)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Tracks assignments and checks for hardcoded credentials."""
        # SEC-005: Hardcoded credentials detection
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name_lower = target.id.lower()
                if self.current_function:
                    self.function_assigned_vars[self.current_function].add(target.id)

                if any(sus in var_name_lower for sus in SUSPICIOUS_VARIABLE_NAMES):
                    # Check if assigned to non-empty literal string
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        val = node.value.value
                        # Disregard obvious placeholders / empty strings
                        if len(val) >= 8 and not any(p in val.lower() for p in ("todo", "dummy", "placeholder", "env", "test")):
                            self.security_findings.append(SecurityFinding(
                                rule_id="SEC-005",
                                severity=IssueSeverity.WARNING,
                                message=f"Suspected hardcoded credential assigned to variable '{target.id}'.",
                                lineno=node.lineno,
                                col_offset=node.col_offset,
                                code_snippet=self._get_snippet(node.lineno),
                            ))

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Tracks variable references for dead code analysis."""
        if isinstance(node.ctx, ast.Load) and self.current_function:
            self.function_referenced_vars[self.current_function].add(node.id)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Checks for bare except handlers and empty except blocks."""
        # SEC-004: Bare except clause
        if node.type is None:
            self.security_findings.append(SecurityFinding(
                rule_id="SEC-004",
                severity=IssueSeverity.WARNING,
                message="Bare 'except:' catches BaseException, hiding KeyboardInterrupt and SystemExit.",
                lineno=node.lineno,
                col_offset=node.col_offset,
                code_snippet=self._get_snippet(node.lineno),
            ))

        # SMELL-004: Empty except block
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.code_smells.append(CodeSmell(
                rule_id="SMELL-004",
                message="Exception handler contains only 'pass' (silent failure / error masking).",
                lineno=node.lineno,
                category="ErrorHandling",
            ))

        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Detects TYPE_CHECKING guards to classify imports accurately."""
        is_type_guard = False
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            is_type_guard = True
        elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
            is_type_guard = True

        if is_type_guard:
            self.in_type_checking_guard = True
            for stmt in node.body:
                self.visit(stmt)
            self.in_type_checking_guard = False
            for stmt in node.orelse:
                self.visit(stmt)
        else:
            self.generic_visit(node)

    def _get_snippet(self, lineno: int) -> Optional[str]:
        """Returns the source line text for error diagnostics."""
        idx = lineno - 1
        if 0 <= idx < len(self.source_lines):
            return self.source_lines[idx].strip()
        return None


# =====================================================================
# Section 6: Maintainability Index Engine
# =====================================================================

class MaintainabilityIndexEngine:
    """Calculates Maintainability Index (MI) using Software Engineering Institute standards.

    Formula:
        MI = 171.0 - 5.2 * ln(Halstead Volume) - 0.23 * Cyclomatic Complexity - 16.2 * ln(SLOC)
    Normalized to 0 - 100 range:
        MI_norm = max(0.0, min(100.0, MI * 100.0 / 171.0))
    """

    @classmethod
    def calculate(
        cls,
        halstead_volume: float,
        cyclomatic_complexity: int,
        source_lines_of_code: int,
    ) -> Tuple[float, MaintainabilityGrade]:
        """Calculates normalized Maintainability Index and assigns letter grade."""
        vol = max(1.0, halstead_volume)
        cc = max(1, cyclomatic_complexity)
        sloc = max(1, source_lines_of_code)

        raw_mi = 171.0 - (5.2 * math.log(vol)) - (0.23 * cc) - (16.2 * math.log(sloc))
        normalized = max(0.0, min(100.0, (raw_mi * 100.0) / 171.0))
        rounded_score = round(normalized, 1)

        if rounded_score >= 65.0:
            grade = MaintainabilityGrade.A
        elif rounded_score >= 40.0:
            grade = MaintainabilityGrade.B
        else:
            grade = MaintainabilityGrade.C

        return rounded_score, grade


# =====================================================================
# Section 7: Source Code SLOC & Comment Counter
# =====================================================================

class SourceLineCounter:
    """Accurately counts raw lines, physical SLOC, comments, and blank lines."""

    @classmethod
    def analyze(cls, source_code: str) -> Dict[str, int]:
        """Breaks down source code lines into exact physical categories."""
        lines = source_code.splitlines()
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0
        code_lines = 0

        in_multiline_string = False
        multiline_delimiter: Optional[str] = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
                continue

            if stripped.startswith("#"):
                comment_lines += 1
                continue

            # Multi-line string detection
            if in_multiline_string:
                comment_lines += 1
                if multiline_delimiter and multiline_delimiter in stripped:
                    in_multiline_string = False
                    multiline_delimiter = None
                continue

            if stripped.startswith('"""') or stripped.startswith("'''"):
                delimiter = stripped[:3]
                if stripped.count(delimiter) == 1:
                    in_multiline_string = True
                    multiline_delimiter = delimiter
                comment_lines += 1
                continue

            code_lines += 1

        return {
            "total_lines": total_lines,
            "sloc": code_lines,
            "blank_lines": blank_lines,
            "comment_lines": comment_lines,
        }


# =====================================================================
# Section 8: The AST Inspector Tool (MCP Interface)
# =====================================================================

class ASTInspectorTool(BaseTool):
    """Production-grade static AST analysis tool for Python code bases.

    Performs comprehensive structural inspection, single-pass AST traversal,
    isolated McCabe cyclomatic complexity, SonarQube cognitive complexity,
    Halstead software metrics, 5-tier argument type checking, and security scans.
    """

    name: str = "ast_inspector"
    description: str = (
        "Statically inspects Python code or files using AST. Extracts classes, "
        "functions, imports, isolated McCabe complexity, cognitive complexity, "
        "type annotation coverage, Halstead software metrics, and security lints."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the Python file to inspect.",
            },
            "source_code": {
                "type": "string",
                "description": "Raw Python source code string to inspect if file_path is omitted.",
            },
            "include_halstead": {
                "type": "boolean",
                "description": "Whether to include Halstead software science metrics (default: True).",
            },
            "include_security": {
                "type": "boolean",
                "description": "Whether to include static security vulnerability scans (default: True).",
            },
        },
        "anyOf": [
            {"required": ["file_path"]},
            {"required": ["source_code"]},
        ],
    }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Executes comprehensive AST static analysis on target source code."""
        file_path = kwargs.get("file_path")
        source_code = kwargs.get("source_code")
        include_halstead = kwargs.get("include_halstead", True)
        include_security = kwargs.get("include_security", True)

        # 1. Parameter Validation
        if not file_path and not source_code:
            return ToolResult(
                success=False,
                error="Schema validation error: Either 'file_path' or 'source_code' must be provided.",
            )

        target_file: Optional[str] = None
        if file_path:
            target_file = os.path.abspath(file_path)
            if not os.path.isfile(target_file):
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path}",
                )
            try:
                with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                    source_code = f.read()
            except OSError as e:
                return ToolResult(
                    success=False,
                    error=f"Failed to read file {file_path}: {e}",
                )

        if source_code is None:
            return ToolResult(success=False, error="Source code is empty or unreadable.")

        # 2. Syntax Tree Parsing
        source_lines = source_code.splitlines()
        try:
            tree = ast.parse(source_code, filename=target_file or "<snippet>")
        except SyntaxError as e:
            col = e.offset or 0
            return ToolResult(
                success=False,
                error=f"SyntaxError in {target_file or '<snippet>'} at line {e.lineno}, col {col}: {e.msg}",
            )

        # 3. Single-Pass AST Traversal
        visitor = SinglePassASTVisitor(source_lines=source_lines, file_path=target_file)
        visitor.visit(tree)

        # 4. SLOC and Physical Line Metrics
        line_stats = SourceLineCounter.analyze(source_code)

        # 5. Type Annotation Coverage Aggregation
        total_funcs = len(visitor.functions)
        fully_typed_funcs = sum(1 for f in visitor.functions if f.is_fully_typed)

        # Total arguments across all functions
        total_args_all = sum(f.total_args_count for f in visitor.functions)
        typed_args_all = sum(f.typed_args_count for f in visitor.functions)
        returns_annotated = sum(1 for f in visitor.functions if f.has_return_type)

        # Edge Case 6 Fix: Empty function set returns 0.0 to prevent metric inflation
        type_coverage = round((fully_typed_funcs / total_funcs) * 100.0, 1) if total_funcs > 0 else 0.0
        arg_type_coverage = round((typed_args_all / total_args_all) * 100.0, 1) if total_args_all > 0 else 0.0
        return_type_coverage = round((returns_annotated / total_funcs) * 100.0, 1) if total_funcs > 0 else 0.0

        # 6. Complexity Statistics
        complexities = [f.cyclomatic_complexity for f in visitor.functions]
        avg_cc = round(sum(complexities) / len(complexities), 2) if complexities else 1.0
        max_cc = max(complexities) if complexities else 1

        cognitive_scores = [f.cognitive_complexity for f in visitor.functions]
        avg_cog = round(sum(cognitive_scores) / len(cognitive_scores), 2) if cognitive_scores else 0.0
        max_cog = max(cognitive_scores) if cognitive_scores else 0

        # 7. Halstead & Maintainability Index Calculation
        halstead_metrics = visitor.halstead_collector.build_metrics()
        mi_score, mi_grade = MaintainabilityIndexEngine.calculate(
            halstead_volume=halstead_metrics.volume,
            cyclomatic_complexity=max_cc,
            source_lines_of_code=line_stats["sloc"],
        )

        # 8. Assemble Data Payloads (Preserves 100% Backwards Compatibility)
        classes_data = [c.to_dict() for c in visitor.classes]
        functions_data = [f.to_dict() for f in visitor.functions]
        imports_data = [i.to_dict() for i in visitor.imports]
        security_data = [s.to_dict() for s in visitor.security_findings] if include_security else []
        smells_data = [m.to_dict() for m in visitor.code_smells]

        data: Dict[str, Any] = {
            # Backward-compatible keys
            "file_path": target_file,
            "line_count": line_stats["total_lines"],
            "class_count": len(classes_data),
            "function_count": total_funcs,
            "import_count": len(imports_data),
            "type_coverage_pct": type_coverage,
            "classes": classes_data,
            "functions": functions_data,
            "imports": imports_data,
            # Enhanced production metrics
            "sloc": line_stats["sloc"],
            "blank_lines": line_stats["blank_lines"],
            "comment_lines": line_stats["comment_lines"],
            "argument_type_coverage_pct": arg_type_coverage,
            "return_type_coverage_pct": return_type_coverage,
            "average_cyclomatic_complexity": avg_cc,
            "max_cyclomatic_complexity": max_cc,
            "average_cognitive_complexity": avg_cog,
            "max_cognitive_complexity": max_cog,
            "maintainability_index": mi_score,
            "maintainability_grade": mi_grade.value,
            "security_findings_count": len(security_data),
            "code_smells_count": len(smells_data),
            "security_findings": security_data,
            "code_smells": smells_data,
        }

        if include_halstead:
            data["halstead"] = halstead_metrics.to_dict()

        return ToolResult(
            success=True,
            data=data,
            metadata={
                "tool": self.name,
                "parsed_nodes": halstead_metrics.length,
                "visitor_mode": "single_pass_o_n",
                "maintainability_grade": mi_grade.value,
            },
        )

    def generate_markdown_report(self, analysis_data: Dict[str, Any]) -> str:
        """Formats analysis output into an executive Markdown report."""
        fp = analysis_data.get("file_path") or "<in-memory-snippet>"
        lines = [
            f"# AST Static Analysis Report: `{os.path.basename(fp)}`",
            "",
            "## Summary Metrics",
            f"- **Physical Lines:** {analysis_data.get('line_count', 0)} (SLOC: {analysis_data.get('sloc', 0)})",
            f"- **Classes:** {analysis_data.get('class_count', 0)}",
            f"- **Functions:** {analysis_data.get('function_count', 0)}",
            f"- **Imports:** {analysis_data.get('import_count', 0)}",
            f"- **Type Coverage:** {analysis_data.get('type_coverage_pct', 0.0)}%",
            f"- **Maintainability Index:** {analysis_data.get('maintainability_index', 0.0)} (Grade: {analysis_data.get('maintainability_grade', 'N/A')})",
            f"- **Avg / Max Cyclomatic Complexity:** {analysis_data.get('average_cyclomatic_complexity', 1.0)} / {analysis_data.get('max_cyclomatic_complexity', 1)}",
            f"- **Avg / Max Cognitive Complexity:** {analysis_data.get('average_cognitive_complexity', 0.0)} / {analysis_data.get('max_cognitive_complexity', 0)}",
            "",
        ]

        # Security Findings
        findings = analysis_data.get("security_findings", [])
        lines.append(f"## Security Findings ({len(findings)})")
        if not findings:
            lines.append("- Zero security issues detected.")
        else:
            for f in findings:
                lines.append(f"- **[{f['severity']}] {f['rule_id']}** (Line {f['line_number']}): {f['message']}")
        lines.append("")

        # Code Smells
        smells = analysis_data.get("code_smells", [])
        lines.append(f"## Code Smells ({len(smells)})")
        if not smells:
            lines.append("- Zero code smells detected.")
        else:
            for s in smells:
                lines.append(f"- **{s['rule_id']}** (Line {s['line_number']}): {s['message']}")
        lines.append("")

        return "\n".join(lines)
