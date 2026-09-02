"""
Saleha Core: Real Test Runner (A1 -- honesty gap fix)

Pehle "Tester" sirf syntax/safety check karta tha -- unittest suites kabhi
EXECUTE nahi hoti thi (README claim vs reality gap). Ye module asli mein:

1. User code + test code ko ek runner script me compose karta hai
2. Sandboxed CodeExecutor se chalata hai
3. unittest results ko structured JSON me parse karta hai:
   ran / failures / errors / tracebacks (healer ko feed hone ke liye)

Runner script user code ko concatenate karta hai (tests same namespace ke
names reference karte hain), lekin `if __name__ == "__main__": unittest.main()`
guard-blocks strip kar deta hai warna wo hamara JSON emitter hijack kar lete.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

TEST_JSON_MARKER = "SALEHA_TEST_JSON:"
_MAX_TRACEBACK_CHARS = 1200
_MAX_RAW_OUTPUT = 20_000

# `if __name__ == "__main__": ...` guard block (unittest.main/pytest.main yahin hota hai)
_MAIN_GUARD_RE = re.compile(
    r"^[ \t]*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:[ \t]*\n(?:[ \t]+.*\n?)*",
    re.MULTILINE,
)
# Standalone runner invocations (guard ke bahar likhe ho to bhi)
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
        """Healer/reflexion prompts ke liye compact failure text."""
        if self.error:
            return self.error
        parts = []
        for f in self.failures[:3]:
            tb = f.traceback[-_MAX_TRACEBACK_CHARS:]
            parts.append(f"--- {f.test_name} ---\n{tb}")
        report = "\n".join(parts) or "No failure details captured."
        return report[:max_chars]


def sanitize_test_code(test_code: str) -> str:
    """__main__ guards aur standalone runner calls hatao."""
    cleaned = _MAIN_GUARD_RE.sub("", test_code or "")
    cleaned = _STANDALONE_RUNNER_RE.sub("", cleaned)
    return cleaned.strip()


def build_runner_script(code: str, test_code: str) -> str:
    """Executable script: solution + tests + structured JSON emitter."""
    safe_tests = sanitize_test_code(test_code)
    return (
        "# ===== Saleha Under-Test (solution) =====\n"
        f"{code.rstrip()}\n\n"
        "# ===== Saleha Test Suite =====\n"
        f"{safe_tests}\n\n"
        "# ===== Saleha Structured Runner (auto-generated) =====\n"
        "import io as _io, json as _json, sys as _sys, unittest as _unittest\n"
        "_stream = _io.StringIO()\n"
        "_suite = _unittest.defaultTestLoader.loadTestsFromModule(_sys.modules[__name__])\n"
        "_result = _unittest.TextTestRunner(stream=_stream, verbosity=0).run(_suite)\n"
        "_combined = list(_result.failures) + list(_result.errors)\n"
        "_payload = {\n"
        "    'ran': _result.testsRun,\n"
        "    'skipped': len(getattr(_result, 'skipped', [])),\n"
        "    'failures': [\n"
        "        {'test': str(t), 'traceback': (tb or '')[-"
        + str(_MAX_TRACEBACK_CHARS) + ":]}\n"
        "        for t, tb in _combined\n"
        "    ],\n"
        "}\n"
        f"print({TEST_JSON_MARKER!r} + _json.dumps(_payload))\n"
        "_sys.exit(0 if _result.wasSuccessful() else 1)\n"
    )


class TestRunner:
    """unittest suites ko sach mein execute karta hai (sandboxed).

    Security model: user segments (solution + tests) ko hum KHUD
    safety_patterns se validate karte hain -- dono segments blocked-import ya
    dangerous-pattern free hone chahiye. Phir combined script
    `allow_dangerous=True` ke saath chalta hai kyunki uska sirf extra hissa
    hamara trusted harness-footer hai (io/json/sys/unittest -- result
    reporting tak simit, koi network/filesystem access nahi). Pehle poora
    script generic check hota tha jisme hamara hi harness `sys` import par
    block ho jaata tha.
    """
    __test__ = False

    def __init__(self, executor=None):
        # Lazy import: code_executor chain heavy-ish hai
        from saleha.core.code_executor import CodeExecutor
        self.executor = executor or CodeExecutor(timeout=15)

    def _validate_segment(self, label: str, segment: str) -> Optional[str]:
        if not segment or not segment.strip():
            return None
        from saleha.core.safety_patterns import check_dangerous, _check_blocked_imports

        danger = check_dangerous(segment)
        if danger:
            return f"{label}: {danger.description} (pattern: '{danger.pattern}')"
        blocked = _check_blocked_imports(segment)
        if blocked:
            return f"{label}: {blocked}"
        return None

    def run_suite(self, code: str, test_code: Optional[str] = None,
                  timeout: Optional[int] = None) -> TestSuiteResult:
        """test_code diya ho to full unittest execution, warna bare runtime
        smoke-test (exit-code based)."""
        effective_timeout = timeout or getattr(self.executor, "timeout", 15)

        if test_code and test_code.strip():
            # Dono user segments ki apni validation (executor-level generic
            # check skip hoga, ye replacement hai -- bypass nahi)
            for label, segment in (("solution", code), ("tests", test_code)):
                violation = self._validate_segment(label, segment)
                if violation:
                    return TestSuiteResult(
                        passed=False, blocked=True,
                        error=f"Blocked by safety layer: {violation}",
                    )
            script = build_runner_script(code, test_code)
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
            # Bare smoke: exit-code hi verdict hai
            result.passed = exec_res.success
            if not exec_res.success:
                result.error = exec_res.error or exec_res.output or f"exit {exec_res.exit_code}"
            return result

        marker_line = self._extract_marker(result.raw_output)
        if marker_line is None:
            # Script crash hua JSON print se pehle (import error / syntax / timeout)
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
        result.passed = exec_res.success and not result.failures
        if not result.passed and not result.failures and not exec_res.success:
            result.error = exec_res.error or f"runner exit {exec_res.exit_code}"
        return result

    @staticmethod
    def _extract_marker(output: str) -> Optional[str]:
        for line in reversed((output or "").splitlines()):
            line = line.strip()
            if line.startswith(TEST_JSON_MARKER):
                return line[len(TEST_JSON_MARKER):]
        return None
