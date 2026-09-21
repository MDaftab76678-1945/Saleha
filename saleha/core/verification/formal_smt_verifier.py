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

What this module does:
1. For each division/modulo whose divisor is a single variable or linear arithmetic
   expression (`b`, `b + 1`, `x - y`), it looks for guards on those variables earlier
   in the same function, and asks Z3 whether those guards imply the divisor cannot be zero.
2. For each `seq[idx]` subscript where `idx` is a single variable or linear index
   expression (`i`, `i + 1`, `i - 1`), it asks Z3 whether guards earlier in the function
   imply `0 <= idx < len(seq)`.

What this still cannot do, and says so rather than pretending otherwise:
- Non-linear arithmetic expressions (e.g. `a / (b * b + 1)`, exponentiation) or function
  calls inside divisors/subscripts are reported as "not analyzed", not as safe.
- Only guards expressible as comparisons (or `and`/`or` of comparisons) between
  variables, linear arithmetic, constants, or `len(seq)` are understood.
- Index bounds checking assumes `len(seq)` at the guard site still holds the
  same value at the subscript site (no mutation of `seq`'s length in between is tracked).
- There is no whole-program precondition/postcondition proof, no loop invariant proof,
  and no Hoare-logic verification of anything beyond these two obligations.
- If the ``z3-solver`` package is not installed, no proof is attempted and the result
  says so explicitly instead of falling back to invented text.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

try:
    import z3  # type: ignore

    Z3_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    class _Z3Fallback:
        def __getattr__(self, name: str) -> Any:
            return None

    z3: Any = _Z3Fallback()
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


def _node_to_z3_arith(
    node: ast.AST,
    env: Dict[str, Any],
    len_terms: Optional[Dict[str, Any]] = None,
    is_real: bool = False,
) -> Optional[Any]:
    """Translates an AST node (variable, constant, len() call, or linear binop) into a Z3 arithmetic term."""
    if isinstance(node, ast.Name):
        if node.id not in env:
            env[node.id] = z3.Real(node.id) if is_real else z3.Int(node.id)
        return env[node.id]

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        sub = _node_to_z3_arith(node.operand, env, len_terms, is_real=is_real)
        return -sub if sub is not None else None

    if (
        len_terms
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "len"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
    ):
        return len_terms.get(node.args[0].id)

    if isinstance(node, ast.BinOp):
        left = _node_to_z3_arith(node.left, env, len_terms, is_real=is_real)
        right = _node_to_z3_arith(node.right, env, len_terms, is_real=is_real)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right

    return None


def _guard_to_z3(
    node: ast.AST,
    var: Any,
    var_name: Optional[str] = None,
    len_terms: Optional[Dict[str, Any]] = None,
    is_real: bool = False,
) -> Optional[Any]:
    """Translates boolean expressions into Z3 constraints.

    Supports single variables, linear arithmetic expressions, chained comparisons,
    and logical connectives (Not, And, Or). Backwards-compatible with (node, var, var_name, len_terms).
    """
    if isinstance(var, dict):
        env = var
    else:
        env = {var_name: var} if var_name else {}

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _guard_to_z3(node.operand, env, var_name, len_terms, is_real=is_real)
        return None if inner is None else z3.Not(inner)

    if isinstance(node, ast.BoolOp):
        parts = [_guard_to_z3(v, env, var_name, len_terms, is_real=is_real) for v in node.values]
        if any(p is None for p in parts):
            return None
        if isinstance(node.op, ast.And):
            return z3.And(*parts)
        return z3.Or(*parts)

    if isinstance(node, ast.Compare) and len(node.ops) > 1:
        operands = [node.left] + list(node.comparators)
        parts = []
        for i, op in enumerate(node.ops):
            pair = ast.Compare(left=operands[i], ops=[op], comparators=[operands[i + 1]])
            parts.append(_guard_to_z3(pair, env, var_name, len_terms, is_real=is_real))
        if any(p is None for p in parts):
            return None
        return z3.And(*parts)

    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left_z3 = _node_to_z3_arith(node.left, env, len_terms, is_real=is_real)
        right_z3 = _node_to_z3_arith(node.comparators[0], env, len_terms, is_real=is_real)
        if left_z3 is None or right_z3 is None:
            return None

        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left_z3 == right_z3
        if isinstance(op, ast.NotEq):
            return left_z3 != right_z3
        if isinstance(op, ast.Lt):
            return left_z3 < right_z3
        if isinstance(op, ast.LtE):
            return left_z3 <= right_z3
        if isinstance(op, ast.Gt):
            return left_z3 > right_z3
        if isinstance(op, ast.GtE):
            return left_z3 >= right_z3

    return None


def _find_guards_for(
    func_node: ast.FunctionDef, var_names: Set[str], before_line: int
) -> List[ast.AST]:
    """Finds every `assert`/early-exit guard mentioning any of `var_names` before `before_line`."""
    found: List[ast.AST] = []
    for node in ast.walk(func_node):
        if not hasattr(node, "lineno") or node.lineno >= before_line:
            continue
        if isinstance(node, ast.Assert):
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if names.intersection(var_names):
                found.append(node.test)
        elif isinstance(node, ast.If):
            exits_early = any(isinstance(s, (ast.Raise, ast.Return)) for s in node.body)
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if exits_early and names.intersection(var_names):
                # An early-exit `if cond: raise` guards the *negation* of
                # its test for any code that runs after the if-block.
                found.append(ast.UnaryOp(op=ast.Not(), operand=node.test))
    return found


def _find_guard_for(func_node: ast.FunctionDef, var_name: str, before_line: int) -> Optional[ast.AST]:
    """Finds the nearest `assert <cond>` or `if <cond>: raise/return` guarding `var_name`."""
    guards = _find_guards_for(func_node, {var_name}, before_line)
    return guards[-1] if guards else None


def _find_index_guards(
    func_node: ast.FunctionDef, index_name: str, before_line: int
) -> List[ast.AST]:
    """Finds every `assert`/early-exit guard mentioning `index_name` before `before_line`."""
    return _find_guards_for(func_node, {index_name}, before_line)


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

            divisor_str = ast.unparse(divisor)
            var_names = {n.id for n in ast.walk(divisor) if isinstance(n, ast.Name)}
            if not var_names:
                checks.append(DivisionCheck(
                    node.lineno, divisor_str, "not_analyzed",
                    f"Divisor '{divisor_str}' contains no variable names to analyze.",
                ))
                continue

            env: Dict[str, Any] = {name: z3.Real(name) for name in var_names}
            divisor_z3 = _node_to_z3_arith(divisor, env, is_real=True)
            if divisor_z3 is None:
                checks.append(DivisionCheck(
                    node.lineno, divisor_str, "not_analyzed",
                    f"Divisor '{divisor_str}' uses an expression form this checker cannot translate to Z3.",
                ))
                continue

            guard_asts = _find_guards_for(func_node, var_names, node.lineno)
            if not guard_asts:
                names_fmt = ", ".join(sorted(var_names))
                checks.append(DivisionCheck(
                    node.lineno, divisor_str, "not_proven",
                    f"No assert or early-exit guard on '{names_fmt}' found before this line.",
                ))
                continue

            guard_exprs = [_guard_to_z3(g, env, is_real=True) for g in guard_asts]
            if any(g is None for g in guard_exprs):
                names_fmt = ", ".join(sorted(var_names))
                checks.append(DivisionCheck(
                    node.lineno, divisor_str, "not_analyzed",
                    f"A guard on '{names_fmt}' uses a form this checker cannot translate to Z3.",
                ))
                continue

            solver = z3.Solver()
            for g in guard_exprs:
                solver.add(g)
            solver.add(divisor_z3 == 0)
            result = solver.check()
            if result == z3.unsat:
                names_fmt = ", ".join(sorted(var_names))
                checks.append(DivisionCheck(
                    node.lineno, divisor_str, "proven_safe",
                    f"Z3 proved the guard(s) on '{names_fmt}' rule out zero (UNSAT for guard AND {divisor_str}=0).",
                ))
            else:
                names_fmt = ", ".join(sorted(var_names))
                checks.append(DivisionCheck(
                    node.lineno, divisor_str, "not_proven",
                    f"Z3 found the guard(s) on '{names_fmt}' do not rule out zero (result: {result}).",
                ))

        index_checks: List[IndexBoundsCheck] = []
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.value, ast.Name):
                continue  # e.g. self.items[i] -- only bare-name sequences are handled
            seq_name = node.value.id

            index_node = node.slice
            index_str = ast.unparse(index_node)
            var_names = {n.id for n in ast.walk(index_node) if isinstance(n, ast.Name)}
            if not var_names:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, index_str, "not_analyzed",
                    f"Index '{index_str}' contains no variable names to analyze.",
                ))
                continue

            env: Dict[str, Any] = {name: z3.Int(name) for name in var_names}
            z3_len = z3.Int(f"len_{seq_name}")
            len_terms = {seq_name: z3_len}
            index_z3 = _node_to_z3_arith(index_node, env, len_terms=len_terms, is_real=False)
            if index_z3 is None:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, index_str, "not_analyzed",
                    f"Index '{index_str}' uses an expression form this checker cannot translate to Z3.",
                ))
                continue

            guard_asts = _find_guards_for(func_node, var_names.union({seq_name}), node.lineno)
            checks_name = index_str if not isinstance(index_node, ast.Name) else index_node.id
            if not guard_asts:
                names_fmt = ", ".join(sorted(var_names))
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, checks_name, "not_proven",
                    f"No assert or early-exit guard on '{names_fmt}' found before this line.",
                ))
                continue

            guard_exprs = [_guard_to_z3(g, env, len_terms=len_terms, is_real=False) for g in guard_asts]
            if any(g is None for g in guard_exprs):
                names_fmt = ", ".join(sorted(var_names))
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, checks_name, "not_analyzed",
                    f"A guard on '{names_fmt}' uses a form this checker cannot translate to Z3.",
                ))
                continue

            solver = z3.Solver()
            for g in guard_exprs:
                solver.add(g)
            solver.add(z3_len >= 0)
            solver.push()
            solver.add(z3.Or(index_z3 < 0, index_z3 >= z3_len))
            result = solver.check()
            solver.pop()
            if result == z3.unsat:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, checks_name, "proven_safe",
                    f"Z3 proved the guard(s) rule out both {index_str}<0 and {index_str}>=len({seq_name}).",
                ))
            else:
                index_checks.append(IndexBoundsCheck(
                    node.lineno, seq_name, checks_name, "not_proven",
                    f"Z3 found the guard(s) do not rule out an out-of-bounds access (result: {result}).",
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
