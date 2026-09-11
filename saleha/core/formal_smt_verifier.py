"""
Saleha Core: SMT-backed division-safety and index-bounds verifier.

The previous version of this module never called an SMT solver at all. Its
"mathematical_certificate" field literally read
``SMT_Z3_CERTIFICATE_SAT: ... Proof Depth: 64-bit`` for every input, produced
by string formatting after a handful of AST pattern checks -- there was no Z3
import anywhere in the file. That is worse than doing no verification: it
claims a solver-checked guarantee that never happened.

This version does two narrow things for real:

1. For each division/modulo whose divisor is a single variable, it looks for
   a guard on that variable (an ``assert`` or an early ``return``/``raise``
   guarding it) earlier in the same function, and asks Z3 whether that guard
   actually implies the divisor cannot be zero.
2. For each ``seq[i]`` subscript where ``i`` is a single variable and
   ``len(seq)`` appears literally in a guard on ``i`` earlier in the same
   function, it asks Z3 whether that guard actually implies
   ``0 <= i < len(seq)``.

Both are genuine, if narrow, SMT proof obligations, and Z3 either proves them
or does not -- there is no third "probably fine" outcome.

What this still cannot do, and says so rather than pretending otherwise:
- Only division/modulo by, or indexing with, a bare local variable is
  checked. An expression (`a / (b - c)`, `seq[i + 1]`), an attribute, or a
  call is reported as "not analyzed", not as safe.
- Only guards expressible as a comparison (or `and`/`or` of comparisons)
  between that variable and a constant, or (for indexing) `len(seq)`, are
  understood. A guard behind a helper function call is invisible to this
  checker.
- Index bounds checking assumes `len(seq)` at the guard site still holds the
  same value at the subscript site (no mutation of `seq`'s length in
  between is tracked). This is a real limitation of a purely syntactic
  correlation between two program points, not a solver limitation.
- There is no whole-program precondition/postcondition proof, no loop
  invariant proof, and no Hoare-logic verification of anything beyond these
  two obligations. Earlier versions of this module claimed all of those;
  none of them were ever implemented.
- If the ``z3-solver`` package is not installed, no proof is attempted and
  the result says so explicitly instead of falling back to invented text.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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
class IndexBoundsCheck:
    line_number: int
    sequence_name: str
    index_expr: str
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
    index_checks: List[IndexBoundsCheck] = field(default_factory=list)
    index_accesses_found: int = 0
    index_accesses_proven_safe: int = 0
    index_accesses_not_analyzed: int = 0
    proof_duration_ms: float = 0.0
    mathematical_certificate: str = ""


def _guard_to_z3(
    node: ast.AST,
    var: z3.ArithRef,
    var_name: str,
    len_terms: Optional[Dict[str, "z3.ArithRef"]] = None,
) -> Optional["z3.BoolRef"]:
    """Translates a narrow class of boolean expressions into a Z3 constraint.

    Handles comparisons of `var_name` against integer/float constants
    (==, !=, <, <=, >, >=) and `and`/`or` combinations of those. When
    `len_terms` is given (name -> Z3 symbol for `len(name)`), a comparison
    against a literal `len(seq_name)` call is also understood, using the
    matching symbol. Anything else (function calls, attribute access, comparisons against other
    variables) is unsupported and returns None so the caller can report
    "not analyzed" rather than silently ignoring part of the guard.
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _guard_to_z3(node.operand, var, var_name, len_terms)
        return None if inner is None else z3.Not(inner)

    if isinstance(node, ast.BoolOp):
        parts = [_guard_to_z3(v, var, var_name, len_terms) for v in node.values]
        if any(p is None for p in parts):
            return None
        if isinstance(node.op, ast.And):
            return z3.And(*parts)
        return z3.Or(*parts)

    if isinstance(node, ast.Compare) and len(node.ops) > 1:
        # Python's chained comparison `a <= b < c` means `a <= b and b < c`,
        # evaluating each operand once. Splitting into pairwise Compare nodes
        # reuses the single-comparison logic below for each link in the
        # chain rather than duplicating it.
        operands = [node.left] + list(node.comparators)
        parts = []
        for i, op in enumerate(node.ops):
            pair = ast.Compare(left=operands[i], ops=[op], comparators=[operands[i + 1]])
            parts.append(_guard_to_z3(pair, var, var_name, len_terms))
        if any(p is None for p in parts):
            return None
        return z3.And(*parts)

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

        def as_len_term(n: ast.AST):
            """Recognizes a literal `len(seq_name)` call and returns its Z3 symbol."""
            if (
                len_terms
                and isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "len"
                and len(n.args) == 1
                and isinstance(n.args[0], ast.Name)
            ):
                return len_terms.get(n.args[0].id)
            return None

        op = node.ops[0]
        if as_name(left) == var_name:
            const = as_const(right)
            if const is None:
                const = as_len_term(right)
        elif as_name(right) == var_name:
            const = as_const(left)
            if const is None:
                const = as_len_term(left)
            # `const OP var` means `var (flipped OP) const` -- e.g. `0 <= i`
            # is `i >= 0`, not `i <= 0`. Swapping the operands without also
            # flipping the operator silently inverted every constant-on-the-
            # left comparison (`5 < i`, `0 <= i < len(seq)`, ...) until this
            # was caught by a chained-comparison index-bounds proof that
            # should have succeeded and instead reported "not proven".
            flip = {
                ast.Lt: ast.Gt(), ast.Gt: ast.Lt(),
                ast.LtE: ast.GtE(), ast.GtE: ast.LtE(),
                ast.Eq: ast.Eq(), ast.NotEq: ast.NotEq(),
            }
            op = flip.get(type(op), op)
        else:
            return None
        if const is None:
            return None

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


def _find_index_guards(
    func_node: ast.FunctionDef, index_name: str, before_line: int
) -> List[ast.AST]:
    """Finds every `assert`/early-exit guard mentioning `index_name` before
    `before_line`, same rule as `_find_guard_for` but collecting all of them
    (not just the nearest) -- a lower bound (`i >= 0`) and an upper bound
    (`i < len(seq)`) are commonly asserted as two separate statements, and
    both are needed to prove the access safe."""
    found: List[ast.AST] = []
    for node in ast.walk(func_node):
        if not hasattr(node, "lineno") or node.lineno >= before_line:
            continue
        if isinstance(node, ast.Assert):
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if index_name in names:
                found.append(node.test)
        elif isinstance(node, ast.If):
            exits_early = any(isinstance(s, (ast.Raise, ast.Return)) for s in node.body)
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if exits_early and index_name in names:
                found.append(ast.UnaryOp(op=ast.Not(), operand=node.test))
    return found


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

        index_checks: List[IndexBoundsCheck] = []
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.value, ast.Name):
                continue  # e.g. self.items[i] -- only bare-name sequences are handled
            seq_name = node.value.id

            index_node = node.slice
            if not isinstance(index_node, ast.Name):
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, ast.unparse(index_node), "not_analyzed",
                    "Index is an expression, not a bare variable; this checker only handles variables.",
                ))
                continue
            index_name = index_node.id

            guard_asts = _find_index_guards(func_node, index_name, node.lineno)
            if not guard_asts:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, index_name, "not_proven",
                    f"No assert or early-exit guard on '{index_name}' found before this line.",
                ))
                continue

            z3_idx = z3.Int(index_name)
            z3_len = z3.Int(f"len_{seq_name}")
            len_terms = {seq_name: z3_len}
            guard_exprs = [_guard_to_z3(g, z3_idx, index_name, len_terms) for g in guard_asts]
            if any(g is None for g in guard_exprs):
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, index_name, "not_analyzed",
                    f"A guard on '{index_name}' uses a form this checker cannot translate to Z3.",
                ))
                continue

            solver = z3.Solver()
            for g in guard_exprs:
                solver.add(g)
            # A real len() is never negative; without this, Z3 can satisfy
            # "len_seq < 0 AND index >= len_seq" trivially and the proof
            # below would wrongly fail to hold for every input.
            solver.add(z3_len >= 0)
            solver.push()
            solver.add(z3.Or(z3_idx < 0, z3_idx >= z3_len))
            # If "all guards AND (index < 0 OR index >= len(seq))" is
            # unsatisfiable, the guards prove the index is in bounds.
            result = solver.check()
            solver.pop()
            if result == z3.unsat:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, index_name, "proven_safe",
                    f"Z3 proved the guard(s) on '{index_name}' rule out both "
                    f"{index_name}<0 and {index_name}>=len({seq_name}).",
                ))
            else:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, index_name, "not_proven",
                    f"Z3 found the guard(s) on '{index_name}' do not rule out an "
                    f"out-of-bounds access (result: {result}).",
                ))

        proven = sum(1 for c in checks if c.status == "proven_safe")
        not_analyzed = sum(1 for c in checks if c.status == "not_analyzed")
        idx_proven = sum(1 for c in index_checks if c.status == "proven_safe")
        idx_not_analyzed = sum(1 for c in index_checks if c.status == "not_analyzed")
        duration = round((time.perf_counter() - start_t) * 1000, 2)

        cert_parts = []
        if checks:
            cert_parts.append(
                f"{proven}/{len(checks)} divisions proven safe, "
                f"{not_analyzed} not analyzed"
            )
        if index_checks:
            cert_parts.append(
                f"{idx_proven}/{len(index_checks)} index accesses proven in-bounds, "
                f"{idx_not_analyzed} not analyzed"
            )
        if cert_parts:
            cert = f"Z3 proof check for '{function_name}': " + "; ".join(cert_parts) + "."
        else:
            cert = f"No division, modulo, or subscript operations found in '{function_name}'; nothing to prove."

        return FormalProofContract(
            function_name=function_name,
            z3_available=True,
            divisions_found=len(checks),
            divisions_proven_safe=proven,
            divisions_not_analyzed=not_analyzed,
            checks=checks,
            index_checks=index_checks,
            index_accesses_found=len(index_checks),
            index_accesses_proven_safe=idx_proven,
            index_accesses_not_analyzed=idx_not_analyzed,
            proof_duration_ms=duration,
            mathematical_certificate=cert,
        )


formal_smt_verifier = FormalSMTVerifier()
