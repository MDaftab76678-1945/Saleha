"""
Saleha Agents: Tester Agent (v2.0 -- Real Test Execution)

v1.3 problem: "Tester" only did AST syntax + safety + keyword checks --
unittest suites were never EXECUTED. Now `run_suite()` performs real
execution (via core/test_runner.py), and structured failure tracebacks
reach the healer.

The static `test_code()` remains a fast pre-flight gate (before execution).
"""

import ast
from dataclasses import dataclass
from typing import Optional, List

from saleha.core.safety_patterns import check_dangerous


@dataclass
class TestResult:
    passed: bool
    error_message: str = ""
    error_type: str = "None"


class TesterAgent:
    """Code checker: static pre-flight (AST/safety/keywords) + REAL test
    execution via run_suite()."""
    __test__ = False

    def test_code(self, code: str, expected_keywords: Optional[List[str]] = None,
                  language: str = "python") -> TestResult:
        """
        Validates code syntax, safety, and semantic requirements.
        For non-Python languages, Python AST check is bypassed and polyglot
        SAST scanner is used.
        """
        if not code or not code.strip():
            return TestResult(passed=False, error_message="Code is empty.", error_type="EmptyCode")

        # 1. Syntax Check (Python uses AST parser; other languages checked by their compilers/SAST)
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                return TestResult(
                    passed=False,
                    error_message=f"Syntax Error: line {e.lineno}, {e.msg}",
                    error_type="SyntaxError"
                )

        # 2. Security Check (shared dangerous patterns + SAST)
        danger = check_dangerous(code)
        if danger:
            return TestResult(
                passed=False,
                error_message=f"Security Risk: {danger.description} (pattern: '{danger.pattern}')",
                error_type="SecurityViolation"
            )

        if language != "python":
            from saleha.core.security_scanner import ASTSecurityScanner
            scanner = ASTSecurityScanner()
            ext_map = {"javascript": ".js", "typescript": ".ts", "go": ".go", "rust": ".rs", "java": ".java"}
            vulns = scanner.scan_code(code, filename=f"code{ext_map.get(language, '.txt')}")
            high_vulns = [v for v in vulns if v.severity == "HIGH"]
            if high_vulns:
                return TestResult(
                    passed=False,
                    error_message=f"Security Risk ({high_vulns[0].rule_id}): {high_vulns[0].description}",
                    error_type="SecurityViolation"
                )

        # 3. Semantic Check
        if expected_keywords:
            code_lower = code.lower()
            missing_keywords = [kw for kw in expected_keywords if kw.lower() not in code_lower]

            if missing_keywords:
                return TestResult(
                    passed=False,
                    error_message=f"Semantic Mismatch: required keywords not found: {missing_keywords}",
                    error_type="SemanticError"
                )

        return TestResult(passed=True, error_message="", error_type="None")

    def run_suite(self, code: str, test_code: Optional[str] = None, timeout: int = 15,
                  expected_keywords: Optional[List[str]] = None, language: str = "python"):
        """REAL execution: if the static gate passes, runs the test suite
        (or a bare smoke-test) in the sandbox.

        Returns core.test_runner.TestSuiteResult -- .passed / .failures /
        .failure_report() for healer prompts.
        """
        from saleha.core.test_runner import TestRunner, TestSuiteResult, SuiteFailure

        static = self.test_code(code, expected_keywords, language=language)
        if not static.passed:
            blocked = static.error_type == "SecurityViolation"
            return TestSuiteResult(
                passed=False, error=f"{static.error_type}: {static.error_message}",
                blocked=blocked,
            )

        if language != "python":
            from saleha.core.polyglot_executor import PolyglotExecutor
            poly_exec = PolyglotExecutor(timeout=timeout)
            exec_res = poly_exec.execute(code, language=language)
            failures = []
            if not exec_res.success:
                failures.append(SuiteFailure(test_name=f"{language}_execution", traceback=exec_res.error or exec_res.output))
            return TestSuiteResult(
                passed=exec_res.success,
                ran=1,
                failures=failures,
                raw_output=exec_res.output,
                blocked=exec_res.blocked,
                error=exec_res.block_reason if exec_res.blocked else exec_res.error,
                backend="polyglot",
            )

        runner = getattr(self, "_runner", None)
        if runner is None:
            runner = TestRunner()
            self._runner = runner
        if timeout is not None and hasattr(runner.executor, "timeout"):
            runner.executor.timeout = timeout
        return runner.run_suite(code, test_code=test_code)


if __name__ == "__main__":
    print("=" * 70)
    print("SALEHA TESTER AGENT - SHARED SAFETY PATTERNS TEST")
    print("=" * 70)

    tester = TesterAgent()

    test_cases = [
        {
            "name": "Valid Code with Keywords",
            "code": "def read_file(path):\n    f = open(path)\n    content = f.read()\n    f.close()\n    return content",
            "keywords": ["open", "read", "file"]
        },
        {
            "name": "Wrong Code (No Keywords)",
            "code": "def add(a, b):\n    return a + b",
            "keywords": ["open", "read", "file"]
        },
        {
            "name": "Valid Syntax, No Keywords Check",
            "code": "def hello():\n    print('Hello')",
            "keywords": None
        },
        {
            "name": "Destructive Filesystem Code (from code_executor's old list -- now caught here too)",
            "code": "import shutil\nshutil.rmtree('/')",
            "keywords": None
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test {i}] {test['name']}")
        c_str = str(test["code"])
        kw = test.get("keywords")
        kw_list: Optional[List[str]] = kw if isinstance(kw, list) else None
        result = tester.test_code(c_str, kw_list)
        if result.passed:
            print("PASSED")
        else:
            print(f"FAILED: {result.error_type} - {result.error_message}")