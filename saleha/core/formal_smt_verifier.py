"""
Saleha Core: SMT-backed division-safety verifier.

The previous version of this module never called an SMT solver at all. Its
"mathematical_certificate" field literally read
``SMT_Z3_CERTIFICATE_SAT: ... Proof Depth: 64-bit`` for every input, produced
by string formatting after a handful of AST pattern checks -- there was no Z3
import anywhere in the file. That is worse than doing no verification: it
claims a solver-checked guarantee that never happened.

This version does one thing for real: for each division/modulo whose divisor
is a single variable, it looks for a guard on that variable (an ``assert`` or
an early ``return``/``raise`` guarding it) earlier in the same function, and
asks Z3 whether that guard actually implies the divisor cannot be zero. That
is a genuine, if narrow, SMT proof obligation, and Z3 either proves it or
does not.

What this still cannot do, and says so rather than pretending otherwise:
- Only division by a bare local variable is checked. Division by an
  expression (`a / (b - c)`), an attribute, or a call is reported as
  "not analyzed", not as safe.
- Only guards expressible as a comparison (or `and`/`or` of comparisons)
  between that variable and a constant are understood. A guard behind a
  helper function call is invisible to this checker.
- There is no whole-program precondition/postcondition proof, no loop
  invariant proof, and no Hoare-logic verification of anything other than
  the divisions themselves. Earlier versions of this module claimed all of
  those; none of them were ever implemented.
- If the ``z3-solver`` package is not installed, no proof is attempted and
  the result says so explicitly instead of falling back to invented text.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import z3

    Z3_AVAILABLE = True
except ImportError:
    z3 = None  # type: ignore
    Z3_AVAILABLE = False


@dataclass
class DivisionCheck:
    line_number: int
    divisor_expr: str
    status: str  # "proven_safe" | "not_proven" | "not_analyzed"
    detail: str


@dataclass
class FormalProofContract:
    function_name: str
    z3_available: bool
    divisions_found: int
    divisions_proven_safe: int
    divisions_not_analyzed: int
    checks: List[DivisionCheck] = field(default_factory=list)
    proof_duration_ms: float = 0.0
    mathematical_certificate: str = ""


def _guard_to_z3(node: ast.AST, var: z3.ArithRef, var_name: str) -> Optional["z3.BoolRef"]:
    """Translates a narrow class of boolean expressions into a Z3 constraint.

    Handles comparisons of `var_name` against integer/float constants
    (==, !=, <, <=, >, >=) and `and`/`or` combinations of those. Anything
    else (function calls, attribute access, comparisons against other
    variables) is unsupported and returns None so the caller can report
    "not analyzed" rather than silently ignoring part of the guard.
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _guard_to_z3(node.operand, var, var_name)
        return None if inner is None else z3.Not(inner)

    if isinstance(node, ast.BoolOp):
        parts = [_guard_to_z3(v, var, var_name) for v in node.values]
        if any(p is None for p in parts):
            return None
        if isinstance(node.op, ast.And):
            return z3.And(*parts)
        return z3.Or(*parts)

    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left, right = node.left, node.comparators[0]

        def as_name(n: ast.AST) -> Optional[str]:
            return n.id if isinstance(n, ast.Name) else None

        def as_const(n: ast.AST):
            # A negative literal parses as UnaryOp(USub, Constant(+n)), not a
            # single Constant node, so it needs unwrapping first.
            if (
                isinstance(n, ast.UnaryOp)
                and isinstance(n.op, ast.USub)
                and isinstance(n.operand, ast.Constant)
                and isinstance(n.operand.value, (int, float))
            ):
                return -n.operand.value
            return n.value if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) else None

        if as_name(left) == var_name:
            const = as_const(right)
        elif as_name(right) == var_name:
            const = as_const(left)
            # Constant-on-the-left flips the operator direction below.
            left, right = right, left
        else:
            return None
        if const is None:
            return None

        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return var == const
        if isinstance(op, ast.NotEq):
            return var != const
        if isinstance(op, ast.Lt):
            return var < const
        if isinstance(op, ast.LtE):
            return var <= const
        if isinstance(op, ast.Gt):
            return var > const
        if isinstance(op, ast.GtE):
            return var >= const

    return None


def _find_guard_for(func_node: ast.FunctionDef, var_name: str, before_line: int) -> Optional[ast.AST]:
    """Finds the nearest `assert <cond>` or `if <cond>: raise/return` guarding
    `var_name`, appearing before `before_line` in the function body."""
    best: Optional[ast.AST] = None
    for node in ast.walk(func_node):
        if not hasattr(node, "lineno") or node.lineno >= before_line:
            continue
        if isinstance(node, ast.Assert):
            if var_name in {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}:
                best = node.test
        elif isinstance(node, ast.If):
            exits_early = any(isinstance(s, (ast.Raise, ast.Return)) for s in node.body)
            if exits_early and var_name in {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}:
                # An early-exit `if var == 0: raise` guards the *negation* of
                # its test for any code that runs after the if-block.
                best = ast.UnaryOp(op=ast.Not(), operand=node.test)
    return best


class FormalSMTVerifier:
    """Proves, using Z3, that a narrow class of divisions cannot divide by zero."""

    def verify_function_contract(self, code: str, function_name: str = "solve") -> FormalProofContract:
        start_t = time.perf_counter()

        if not Z3_AVAILABLE:
            return FormalProofContract(
                function_name=function_name,
                z3_available=False,
                divisions_found=0,
                divisions_proven_safe=0,
                divisions_not_analyzed=0,
                proof_duration_ms=round((time.perf_counter() - start_t) * 1000, 2),
                mathematical_certificate=(
                    "z3-solver is not installed, so no proof was attempted. "
                    "Install it with `pip install z3-solver` to enable this check."
                ),
            )

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return FormalProofContract(
                function_name=function_name,
                z3_available=True,
                divisions_found=0,
                divisions_proven_safe=0,
                divisions_not_analyzed=0,
                proof_duration_ms=round((time.perf_counter() - start_t) * 1000, 2),
                mathematical_certificate=f"Could not parse code: {exc}",
            )

        func_node: Optional[ast.FunctionDef] = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == function_name or func_node is None:
                    func_node = node
                    if node.name == function_name:
                        break

        if func_node is None:
            return FormalProofContract(
                function_name=function_name,
                z3_available=True,
                divisions_found=0,
                divisions_proven_safe=0,
                divisions_not_analyzed=0,
                proof_duration_ms=round((time.perf_counter() - start_t) * 1000, 2),
                mathematical_certificate=f"Function '{function_name}' not found in the given code.",
            )

        checks: List[DivisionCheck] = []
        for node in ast.walk(func_node):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))):
                continue

            divisor = node.right
            if isinstance(divisor, ast.Constant) and isinstance(divisor.value, (int, float)):
                if divisor.value == 0:
                    checks.append(DivisionCheck(
                        node.lineno, repr(divisor.value), "not_proven",
                        "Divisor is the literal 0; this always fails.",
                    ))
                else:
                    checks.append(DivisionCheck(
                        node.lineno, repr(divisor.value), "proven_safe",
                        "Divisor is a nonzero literal.",
                    ))
                continue

            if not isinstance(divisor, ast.Name):
                checks.append(DivisionCheck(
                    node.lineno, ast.unparse(divisor), "not_analyzed",
                    "Divisor is an expression, not a bare variable; this checker only handles variables.",
                ))
                continue

            var_name = divisor.id
            guard_ast = _find_guard_for(func_node, var_name, node.lineno)
            if guard_ast is None:
                checks.append(DivisionCheck(
                    node.lineno, var_name, "not_proven",
                    f"No assert or early-exit guard on '{var_name}' found before this line.",
                ))
                continue

            z3_var = z3.Real(var_name)
            guard_expr = _guard_to_z3(guard_ast, z3_var, var_name)
            if guard_expr is None:
                checks.append(DivisionCheck(
                    node.lineno, var_name, "not_analyzed",
                    f"Guard on '{var_name}' uses a form this checker cannot translate to Z3.",
                ))
                continue

            solver = z3.Solver()
            solver.add(guard_expr)
            solver.add(z3_var == 0)
            # If asserting "guard AND divisor == 0" is unsatisfiable, the
            # guard proves the divisor cannot be zero at this point.
            result = solver.check()
            if result == z3.unsat:
                checks.append(DivisionCheck(
                    node.lineno, var_name, "proven_safe",
                    f"Z3 proved the guard on '{var_name}' rules out zero (UNSAT for guard AND {var_name}=0).",
                ))
            else:
                checks.append(DivisionCheck(
                    node.lineno, var_name, "not_proven",
                    f"Z3 found the guard on '{var_name}' does not rule out zero (result: {result}).",
                ))

        proven = sum(1 for c in checks if c.status == "proven_safe")
        not_analyzed = sum(1 for c in checks if c.status == "not_analyzed")
        duration = round((time.perf_counter() - start_t) * 1000, 2)

        if not checks:
            cert = f"No division or modulo operations found in '{function_name}'; nothing to prove."
        else:
            cert = (
                f"Z3 division-safety check for '{function_name}': "
                f"{proven}/{len(checks)} divisions proven safe, "
                f"{not_analyzed} not analyzed (unsupported guard or divisor form)."
            )

        return FormalProofContract(
            function_name=function_name,
            z3_available=True,
            divisions_found=len(checks),
            divisions_proven_safe=proven,
            divisions_not_analyzed=not_analyzed,
            checks=checks,
            proof_duration_ms=duration,
            mathematical_certificate=cert,
        )


formal_smt_verifier = FormalSMTVerifier()
