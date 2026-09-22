"""Decides whether a failing assertion in model-written code blames the test or the code.

A model that writes a function and its own asserts grades itself: a wrong
expected value rejects a correct implementation, and the debugger then tends to
"fix" the wrong side. When a run fails on one checkable assertion -- a call to a
function the code defines, with literal arguments, compared against a literal --
this runs the implementation to get the value it really returns, and asks the
model separately, without showing it the code or the test, what the call should
return for the task. The verdict is only as good as that independent answer: it
is a hint for the debugger, never a pass.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Set, Tuple

RunFn = Callable[[str], Tuple[bool, str]]
AskFn = Callable[[str], str]

_FRAME_RE = re.compile(r'^\s*File "[^"]+", line \d+')
_ANSWER_RE = re.compile(r"^\s*ANSWER:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_VALUE_MARKER = "__saleha_arbiter_value__"
_MISSING = object()

_ORACLE_PROMPT = """Task: {task}

Consider a correct implementation of this task. What exact value does
`{call}` return? Reason briefly, then give the answer on the last line as
ANSWER: <python literal>"""


@dataclass
class FailingExpectation:
    call_src: str
    expected: Any
    assertion_src: str


@dataclass
class ArbitrationVerdict:
    blame: str  # "test" or "implementation"
    expectation: FailingExpectation
    actual: Any
    oracle: Any
    note: str


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _MISSING


def _same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _failing_assertion_sources(error_log: str) -> List[str]:
    lines = error_log.splitlines()
    return [
        lines[i + 1].strip()
        for i, line in enumerate(lines[:-1])
        if _FRAME_RE.match(line) and "assert" in lines[i + 1]
    ]


def _call_and_expected(stmt_src: str, defined: Set[str]) -> Optional[Tuple[ast.Call, Any]]:
    try:
        tree = ast.parse(stmt_src)
    except SyntaxError:
        return None
    if not tree.body:
        return None
    node = tree.body[0]
    target: Optional[ast.AST] = None
    expected: Any = _MISSING

    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            target, expected = test.operand, False
        elif isinstance(test, ast.Compare):
            if len(test.ops) == 1 and isinstance(test.ops[0], (ast.Eq, ast.Is)):
                left, right = test.left, test.comparators[0]
                if isinstance(left, ast.Call):
                    target, expected = left, _literal(right)
                elif isinstance(right, ast.Call):
                    target, expected = right, _literal(left)
        else:
            target, expected = test, True
    elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
          and isinstance(node.value.func, ast.Attribute)):
        method, args = node.value.func.attr, node.value.args
        if method == "assertTrue" and args:
            target, expected = args[0], True
        elif method == "assertFalse" and args:
            target, expected = args[0], False
        elif method in ("assertEqual", "assertIs") and len(args) >= 2:
            if isinstance(args[0], ast.Call):
                target, expected = args[0], _literal(args[1])
            elif isinstance(args[1], ast.Call):
                target, expected = args[1], _literal(args[0])

    if not isinstance(target, ast.Call) or expected is _MISSING:
        return None
    if not (isinstance(target.func, ast.Name) and target.func.id in defined):
        return None
    if any(_literal(a) is _MISSING for a in [*target.args, *(k.value for k in target.keywords)]):
        return None
    return target, expected


def extract_failing_expectation(code: str, error_log: str) -> Optional[FailingExpectation]:
    """The last failing assertion in the traceback that this module can check, if any."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for src in reversed(_failing_assertion_sources(error_log)):
        found = _call_and_expected(src, defined)
        if found:
            call, expected = found
            return FailingExpectation(call_src=ast.unparse(call), expected=expected, assertion_src=src)
    return None


def _is_test_class(node: ast.stmt) -> bool:
    return isinstance(node, ast.ClassDef) and any("TestCase" in ast.unparse(b) for b in node.bases)


def _definitions_only(code: str) -> str:
    tree = ast.parse(code)
    keep: List[ast.stmt] = [
        n for n in tree.body
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.Assign, ast.AnnAssign, ast.ClassDef))
        and not _is_test_class(n)
    ]
    return ast.unparse(ast.Module(body=keep, type_ignores=[]))


def _actual_value(code: str, call_src: str, run: RunFn) -> Any:
    snippet = f"{_definitions_only(code)}\nprint({_VALUE_MARKER!r} + repr({call_src}))\n"
    ok, output = run(snippet)
    if not ok:
        return _MISSING
    for line in reversed(output.splitlines()):
        if line.startswith(_VALUE_MARKER):
            try:
                return ast.literal_eval(line[len(_VALUE_MARKER):])
            except (ValueError, SyntaxError):
                return _MISSING
    return _MISSING


def _oracle_value(task: str, call_src: str, ask: AskFn) -> Any:
    answers = _ANSWER_RE.findall(ask(_ORACLE_PROMPT.format(task=task, call=call_src)) or "")
    if not answers:
        return _MISSING
    try:
        return ast.literal_eval(answers[-1].strip().strip("`"))
    except (ValueError, SyntaxError):
        return _MISSING


def arbitrate_failure(task: str, code: str, error_log: str, run: RunFn, ask: AskFn) -> Optional[ArbitrationVerdict]:
    """Returns a verdict when the independent answer sides with exactly one of
    the test or the implementation; None when it cannot tell."""
    exp = extract_failing_expectation(code, error_log)
    if exp is None:
        return None
    actual = _actual_value(code, exp.call_src, run)
    if actual is _MISSING or _same(actual, exp.expected):
        return None
    oracle = _oracle_value(task, exp.call_src, ask)
    if oracle is _MISSING:
        return None

    if _same(oracle, actual):
        note = (
            f"Independent check: for this task `{exp.call_src}` should return {oracle!r}, "
            f"and the implementation does return {actual!r}. The failing assertion "
            f"`{exp.assertion_src}` expects {exp.expected!r}, so the TEST is wrong: fix or "
            "remove that assertion and keep the implementation's behaviour for this input."
        )
        return ArbitrationVerdict("test", exp, actual, oracle, note)
    if _same(oracle, exp.expected):
        note = (
            f"Independent check: for this task `{exp.call_src}` should return {oracle!r}, "
            f"as the assertion expects, but the implementation returns {actual!r}. "
            "The IMPLEMENTATION is wrong for this input: fix it, not the test."
        )
        return ArbitrationVerdict("implementation", exp, actual, oracle, note)
    return None
