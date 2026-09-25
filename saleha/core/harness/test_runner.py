"""
Saleha Core: Real Test Runner (A1 -- honesty gap fix)

Previously, "Tester" only performed syntax/safety checks -- unittest suites were
never EXECUTED (closing the README claim vs reality gap). This module actually:

1. Composes user code and test code into a unified runner script
2. Executes the combined script via sandboxed CodeExecutor
3. Parses unittest results into structured JSON:
   ran / failures / errors / tracebacks (for consumption by self-healing routines)

The runner script concatenates user code (tests reference names in the same namespace),
while stripping `if __name__ == "__main__": unittest.main()` guard blocks so they do
not hijack our structured JSON emitter.

Three holes closed in pass 159, each measured before the fix:

- The guard was stripped from the *tests* only. A solution ending in
  `if __name__ == "__main__": unittest.main()` -- the shape the Coder writes --
  exited before the runner ran, so a correct `add()` was reported FAILED.
- The result marker was a fixed string. Solution code that printed
  `SALEHA_TEST_JSON:{"ran": 5, "failures": []}` and raised SystemExit(0) made
  a wrong `add()` PASS. The marker now carries a per-run nonce.
- pytest-style `def test_x():` functions were invisible to the unittest
  loader, so such a suite "ran 0 tests". Zero-argument module-level test
  functions are now collected; ones that need pytest fixtures are reported
  as failures, not silently skipped.
"""

from __future__ import annotations

import ast
import json
import re
import secrets
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

TEST_JSON_MARKER = "SALEHA_TEST_JSON:"
_MAX_TRACEBACK_CHARS = 1200
_MAX_RAW_OUTPUT = 20_000

# `if __name__ == "__main__": ...` guard block (matches unittest.main / pytest.main blocks)
_MAIN_GUARD_RE = re.compile(
    r"^[ \t]*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:[ \t]*\n(?:[ \t]+.*\n?)*",
    re.MULTILINE,
)
# Standalone runner invocations outside guards
_STANDALONE_RUNNER_RE = re.compile(
    r"^[ \t]*(?:unittest|pytest)\.main\([^)]*\)[ \t]*$",
    re.MULTILINE,
)


@dataclass
class SuiteFailure:
    test_name: str
    traceback: str


@dataclass
class TestSuiteResult:
    __test__ = False
    passed: bool = False
    ran: int = 0
    failures: List[SuiteFailure] = field(default_factory=list)
    raw_output: str = ""
    blocked: bool = False
    error: str = ""  # infra-level failure (timeout, blocked import, etc.)
    backend: str = "subprocess"

    @property
    def summary(self) -> str:
        if self.error:
            return self.error
        status = "PASSED" if self.passed else "FAILED"
        base = f"{status}: {self.ran - len(self.failures)}/{self.ran} tests"
        if self.failures:
            first = self.failures[0]
            base += f" | first failure: {first.test_name}"
        return base

    def failure_report(self, max_chars: int = 2000) -> str:
        """Compact failure report for self-healing and reflexion prompts."""
        if self.error:
            return self.error
        parts = []
        for f in self.failures[:3]:
            tb = f.traceback[-_MAX_TRACEBACK_CHARS:]
            parts.append(f"--- {f.test_name} ---\n{tb}")
        report = "\n".join(parts) or "No failure details captured."
        return report[:max_chars]


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    cmp = node.test
    if len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq):
        return False
    sides = [cmp.left, cmp.comparators[0]]
    return (any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
            and any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides))


def strip_main_guard(code: str) -> str:
    """
    Remove top-level `if __name__ == "__main__":` blocks from code.

    Generated code ends with its own `unittest.main()` under that guard. Run
    as a script it exits before anything appended after it -- the task's
    tests, the structured runner -- is reached. Code is graded the way an
    importer would use it, which never runs the guard. Everything else is
    left byte-for-byte; unparseable code is returned unchanged and fails on
    its own.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return code
    guards = [n for n in tree.body if _is_main_guard(n)]
    if not guards:
        return code
    lines = code.splitlines()
    for node in guards:
        end = node.end_lineno or node.lineno
        for i in range(node.lineno - 1, end):
            lines[i] = ""
    return "\n".join(lines) + "\n"


def sanitize_test_code(test_code: str) -> str:
    """Strips __main__ guards and standalone runner calls."""
    cleaned = strip_main_guard(test_code or "")
    cleaned = _MAIN_GUARD_RE.sub("", cleaned)
    cleaned = _STANDALONE_RUNNER_RE.sub("", cleaned)
    return cleaned.strip()


def new_result_marker() -> str:
    """A per-run marker the code under test cannot know in advance."""
    return f"{TEST_JSON_MARKER}{secrets.token_hex(8)}:"


def build_runner_script(code: str, test_code: str, marker: Optional[str] = None) -> str:
    """Executable script: solution + tests + structured JSON emitter.

    `marker` should be fresh per run (`new_result_marker()`); the runner
    trusts only a result line carrying it.
    """
    marker = marker or new_result_marker()
    safe_code = _STANDALONE_RUNNER_RE.sub("", strip_main_guard(code or ""))
    safe_code = strip_embedded_testcases(safe_code).rstrip()
    safe_tests = sanitize_test_code(test_code)
    safe_tests = strip_redefinitions(safe_tests, safe_code)
    test_funcs, test_classes, shadowed = _plan_collection(safe_code, safe_tests)
    footer = (
        _RUNNER_FOOTER
        .replace("__TEST_FUNCS__", repr(test_funcs))
        .replace("__TEST_CLASSES__", repr(test_classes))
        .replace("__SHADOWED__", repr(shadowed))
        .replace("__MAX_TB__", str(_MAX_TRACEBACK_CHARS))
        .replace("__MARKER__", repr(marker))
    )
    return (
        "# ===== Saleha Under-Test (solution) =====\n"
        f"{safe_code}\n\n"
        "# ===== Saleha Test Suite =====\n"
        f"{safe_tests}\n\n"
        "# ===== Saleha Structured Runner (auto-generated) =====\n"
        f"{footer}"
    )


def _blank_nodes(source: str, nodes: Sequence[ast.stmt]) -> str:
    """Blank the lines of the given top-level nodes (decorators included); keep the rest byte-for-byte."""
    if not nodes:
        return source
    lines = source.splitlines()
    for node in nodes:
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        for i in range(start - 1, node.end_lineno or node.lineno):
            lines[i] = ""
    return "\n".join(lines) + "\n"


def _is_testcase_class(node: ast.stmt) -> bool:
    if not isinstance(node, ast.ClassDef):
        return False
    for base in node.bases:
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        if name in ("TestCase", "IsolatedAsyncioTestCase"):
            return True
    return False


def strip_embedded_testcases(code: str) -> str:
    """
    Drop unittest.TestCase classes the solution carries with it.

    Generated solutions often end with their own test class. It is not the
    suite, and in a real swarm run one crashed at import (it used `unittest`
    without importing it), failing a correct implementation before a single
    real test ran. The implementation is what gets graded.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return code
    return _blank_nodes(code, [n for n in tree.body if _is_testcase_class(n)])


def strip_redefinitions(tests: str, code: str) -> str:
    """
    Drop top-level functions/classes in the tests that the solution already defines.

    Small models paste the solution into the test file (seen in a real run:
    the QA model redefined `is_palindrome`). Left in place, the tests would
    check the pasted copy, not the solution. Removing the copy makes them
    test the real code.
    """
    code_funcs, code_classes = _top_level_names(code)
    defined = set(code_funcs) | set(code_classes)
    try:
        tree = ast.parse(tests)
    except (SyntaxError, ValueError):
        return tests
    dupes = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name in defined]
    return _blank_nodes(tests, dupes).strip()


def _top_level_names(source: str) -> Tuple[List[str], List[str]]:
    """(function names, class names) defined at the top level of `source`."""
    try:
        body = ast.parse(source).body
    except (SyntaxError, ValueError):
        return [], []  # the script fails on the same syntax error, with the real message
    funcs = [n.name for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n.name for n in body if isinstance(n, ast.ClassDef)]
    return funcs, classes


def _plan_collection(code: str, tests: str) -> Tuple[List[str], List[str], List[str]]:
    """
    What to collect, from the *test* segment only.

    - Tests embedded in the solution are not the suite. Loading the whole
      module used to run the Coder's own TestCase classes too, grading the
      code against its own (sometimes wrong) asserts.
    - A solution helper named test_connection(host) is not a test.
    - A test segment that redefines a solution function or class would test
      its own copy -- seen in a real run: the QA model pasted
      `is_palindrome` into its tests. Those names come back as `shadowed`.
    """
    code_funcs, code_classes = _top_level_names(code)
    test_funcs, test_classes = _top_level_names(tests)
    shadowed = sorted((set(code_funcs) | set(code_classes)) & (set(test_funcs) | set(test_classes)))
    return sorted(f for f in test_funcs if f.startswith("test")), sorted(test_classes), shadowed


# Runs inside the child process after the solution and the tests. Placeholders
# are filled by build_runner_script; everything here is trusted harness code.
_RUNNER_FOOTER = '''import inspect as _inspect, io as _io, json as _json, sys as _sys, unittest as _unittest
_module = _sys.modules[__name__]
_suite = _unittest.TestSuite()
_problems = []


def _required_params(_fn, _skip_self):
    _params = list(_inspect.signature(_fn).parameters.values())[1 if _skip_self else 0:]
    return [p.name for p in _params
            if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]


def _fixture_problem(_label, _names):
    _problems.append({"test": _label, "traceback": "needs pytest fixtures (" + ", ".join(_names)
                      + "); this runner cannot supply them, test not run"})


for _name in __SHADOWED__:
    _problems.append({"test": _name, "traceback": "test code redefines " + repr(_name)
                      + " from the solution, so its tests would check their own copy; suite not run"})

if not _problems:
    for _name in __TEST_FUNCS__:
        _fn = getattr(_module, _name, None)
        if not _inspect.isfunction(_fn):
            continue
        _req = _required_params(_fn, False)
        if _req:
            _fixture_problem(_name, _req)
        else:
            _suite.addTest(_unittest.FunctionTestCase(_fn, description=_name))
    for _name in __TEST_CLASSES__:
        _cls = getattr(_module, _name, None)
        if not _inspect.isclass(_cls):
            continue
        if issubclass(_cls, _unittest.TestCase):
            _suite.addTests(_unittest.defaultTestLoader.loadTestsFromTestCase(_cls))
            continue
        if not _name.startswith("Test"):
            continue  # a helper class, not a pytest-style test class
        for _meth in sorted(n for n in dir(_cls) if n.startswith("test") and callable(getattr(_cls, n))):
            _label = _name + "." + _meth
            _req = _required_params(getattr(_cls, _meth), True)
            if _req:
                _fixture_problem(_label, _req)
                continue

            def _run_method(_c=_cls, _m=_meth):
                getattr(_c(), _m)()

            _suite.addTest(_unittest.FunctionTestCase(_run_method, description=_label))

_result = _unittest.TextTestRunner(stream=_io.StringIO(), verbosity=0).run(_suite)
_combined = list(_result.failures) + list(_result.errors)
_payload = {
    "ran": _result.testsRun,
    "skipped": len(getattr(_result, "skipped", [])),
    "failures": [
        {"test": t.shortDescription() if isinstance(t, _unittest.FunctionTestCase) else str(t),
         "traceback": (tb or "")[-__MAX_TB__:]}
        for t, tb in _combined
    ] + _problems,
}
print(__MARKER__ + _json.dumps(_payload))
_sys.exit(0 if _result.wasSuccessful() and not _problems else 1)
'''


class TestRunner:
    """Executes unittest suites inside an isolated sandbox environment.

    Security model: User segments (solution + tests) are directly validated
    against safety_patterns -- both segments must be free of blocked imports
    and dangerous patterns. The combined runner script is then executed with
    allow_dangerous=True because the only appended code is our trusted harness footer
    (io/json/sys/unittest -- scoped strictly to result reporting with zero network
    or filesystem access).
    """
    __test__ = False

    def __init__(self, executor: Optional[Any] = None) -> None:
        # Lazy import: avoid circular dependencies with code_executor
        from saleha.core.harness.code_executor import CodeExecutor
        self.executor = executor or CodeExecutor(timeout=15)

    def _validate_segment(self, label: str, segment: str) -> Optional[str]:
        if not segment or not segment.strip():
            return None
        from saleha.core.safety_patterns import _check_blocked_imports, check_dangerous

        danger = check_dangerous(segment)
        if danger:
            return f"{label}: {danger.description} (pattern: '{danger.pattern}')"
        blocked = _check_blocked_imports(segment)
        if blocked:
            return f"{label}: {blocked}"
        return None

    def run_suite(self, code: str, test_code: Optional[str] = None,
                  timeout: Optional[int] = None) -> TestSuiteResult:
        """Executes full unittest suite if test_code is provided; otherwise runs a bare smoke test."""
        effective_timeout = timeout or getattr(self.executor, "timeout", 15)
        marker = new_result_marker()

        if test_code and test_code.strip():
            # Validate each user segment individually against safety policy
            for label, segment in (("solution", code), ("tests", test_code)):
                violation = self._validate_segment(label, segment)
                if violation:
                    return TestSuiteResult(
                        passed=False, blocked=True,
                        error=f"Blocked by safety layer: {violation}",
                    )
            script = build_runner_script(code, test_code, marker=marker)
            exec_res = self.executor.execute(script, timeout=effective_timeout,
                                             allow_dangerous=True)
        else:
            exec_res = self.executor.execute(code, timeout=effective_timeout)  # bare smoke

        result = TestSuiteResult(
            raw_output=(exec_res.output or "")[:_MAX_RAW_OUTPUT],
            blocked=exec_res.blocked,
            backend=getattr(exec_res, "backend", "subprocess"),
        )

        if exec_res.blocked:
            result.passed = False
            result.error = f"Blocked by safety layer: {exec_res.block_reason}"
            return result

        if not test_code or not test_code.strip():
            # Bare smoke test: exit code determines success
            result.passed = exec_res.success
            if not exec_res.success:
                result.error = exec_res.error or exec_res.output or f"exit {exec_res.exit_code}"
            return result

        marker_line = self._extract_marker(result.raw_output, marker)
        if marker_line is None:
            # Script crashed prior to emitting JSON marker (import error, syntax, or timeout)
            result.passed = False
            result.error = (
                exec_res.error.strip()
                or exec_res.output.strip()
                or f"suite crashed before reporting (exit {exec_res.exit_code})"
            )[-1500:]
            return result

        try:
            payload = json.loads(marker_line)
        except json.JSONDecodeError as err:
            result.passed = False
            result.error = f"Unparseable test payload: {err}"
            return result

        result.ran = int(payload.get("ran", 0))
        for item in payload.get("failures", []):
            result.failures.append(SuiteFailure(
                test_name=str(item.get("test", "<unknown>")),
                traceback=str(item.get("traceback", "")),
            ))
        if result.ran == 0:
            # test_code was provided but contributed zero actual test methods
            # (e.g. comments-only, malformed test names) -- nothing was verified,
            # so this must not be reported as a pass.
            result.passed = False
            why = f"; {result.failures[0].traceback}" if result.failures else ""
            result.error = result.error or f"test suite ran 0 tests -- nothing was verified{why}"
            return result
        result.passed = exec_res.success and not result.failures
        if not result.passed and not result.failures and not exec_res.success:
            result.error = exec_res.error or f"runner exit {exec_res.exit_code}"
        return result

    @staticmethod
    def _extract_marker(output: str, marker: str = TEST_JSON_MARKER) -> Optional[str]:
        """The payload after `marker`; any other SALEHA_TEST_JSON line is ignored."""
        for line in reversed((output or "").splitlines()):
            line = line.strip()
            if line.startswith(marker):
                return line[len(marker):]
        return None


test_runner = TestRunner()


