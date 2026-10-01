"""
Saleha Agents: Refactor Specialist Agent

Refactors code for a stated goal and checks the refactor did not change
what the code does, as far as a program can tell: the result parses; the
public API (functions, classes, their parameters) is the same; and when
tests are given, they pass on the original AND on the refactor -- only
then is the refactor `verified`. Complexity is measured (decision points
per function, McCabe-style) before and after, not assumed.

The model writes the refactor. Without a model, two safe mechanical
modernisations are applied (typing.List/Dict -> list/dict, Union[A, B] ->
A | B) and checked the same way. The old `x == True` -> `x` and
`x == False` -> `x is False` rewrites were dropped: they change behaviour
for non-bool values (2 == True is False; 0 is False is False).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent

_DECISIONS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith,
              ast.IfExp, ast.comprehension, ast.Assert, ast.Match)


@dataclass
class RefactorResult:
    original_code: str
    refactored_code: str
    complexity_reduced: bool          # measured: total decision points went down
    ast_valid: bool
    transformations_applied: List[str]
    model_used: str = ""
    complexity_before: int = 0
    complexity_after: int = 0
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None   # True: same API and the given tests pass before and after


def complexity(code: str) -> int:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return -1
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, _DECISIONS):
            total += 1
        elif isinstance(node, ast.BoolOp):
            total += len(node.values) - 1
    return total


def public_api(code: str) -> Dict[str, Tuple[str, ...]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    api: Dict[str, Tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            api[node.name] = tuple(a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and (not m.name.startswith("_") or m.name == "__init__")]
            api[node.name] = tuple(sorted(methods))
    return api


def mechanical(code: str) -> Tuple[str, List[str]]:
    out, done = code, []
    if re.search(r"from typing import[^\n]*\b(List|Dict)\b", out):
        new = re.sub(r"\bList\[", "list[", re.sub(r"\bDict\[", "dict[", out))
        if new != out:
            out = new
            done.append("typing.List/Dict -> list/dict (PEP 585)")
    simple_union = re.compile(r"\bUnion\[([\w.]+),\s*([\w.]+)\]")
    if simple_union.search(out):
        out = simple_union.sub(r"\1 | \2", out)
        done.append("Union[A, B] -> A | B (PEP 604), simple names only")
    return out, done


def refactor_checks(original: str, refactored: str, tests: str) -> List[ac.Check]:
    checks = [ac.check_python(refactored, "parses")]
    before, after = public_api(original), public_api(refactored)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    checks.append(ac.Check("same public API", ac.FAIL if changed else ac.PASS,
                           f"changed: {changed}" if changed else f"{len(before)} public name(s) unchanged"))
    if tests.strip():
        base = ac.run_tests(original, tests)
        if base.status != ac.PASS:
            checks.append(ac.Check("tests pass on the original", base.status if base.status == ac.NOT_RUN else ac.FAIL,
                                   f"the tests do not pass before the refactor: {base.detail}"))
        else:
            res = ac.run_tests(refactored, tests)
            checks.append(ac.Check("tests pass after the refactor", res.status, res.detail))
    else:
        checks.append(ac.Check("behaviour preserved", ac.NOT_RUN, "no tests were given to prove it"))
    return checks


class RefactorSpecialistAgent(BaseAgent):
    """Lead Software Refactor & Code Modernization Specialist Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="RefactorSpecialist", model=model)

    def refactor_code(self, task: str, code: str, target_pattern: str = "clean_code", tests: str = "") -> RefactorResult:
        """A refactor for `task`, checked: parses, same API, the given tests pass before and after."""
        prompt = (f"Refactor this Python code. Goal: {task} ({target_pattern.replace('_', ' ')}).\n"
                  "Keep every public function, class and parameter name exactly as it is; change how the code "
                  "works inside, never what it returns.\n"
                  f"```python\n{code[:10000]}\n```\nAnswer with the whole refactored module in one python block.")

        def build(content: str) -> Tuple[str, List[ac.Check]]:
            new = ac.pick(ac.fenced_blocks(content), ("python", "py")) or ""
            return new, refactor_checks(code, new, tests) if new else [ac.Check("parses", ac.FAIL, "no code")]

        new, checks, resp, _rounds = ac.produce(self, prompt, build)
        transforms: List[str]
        if new and ac.verdict([c for c in checks if c.status != ac.NOT_RUN]) is not False:
            refactored, transforms, model_used = new, [f"model refactor for: {task}"], resp.model_used
        else:
            # No model, or its refactor failed a check: the safe mechanical edits only.
            note = ac.fallback_note(checks, new is not None)
            refactored, transforms = mechanical(code)
            checks = note + refactor_checks(code, refactored, tests)
            if ac.check_python(refactored).status != ac.PASS:
                refactored, transforms = code, []
            transforms = transforms or ["no change: nothing the safe edits apply to"]
            model_used = "mechanical (no usable model refactor)"
        before, after = complexity(code), complexity(refactored)
        return RefactorResult(
            original_code=code, refactored_code=refactored,
            complexity_reduced=0 <= after < before, ast_valid=ac.check_python(refactored).status == ac.PASS,
            transformations_applied=transforms, model_used=model_used, complexity_before=before,
            complexity_after=after, checks=ac.as_dicts(checks), verified=ac.artifact_verdict(checks))
