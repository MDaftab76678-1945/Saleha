"""
Saleha Agents: Tester Agent (v2.0 -- Real Test Execution)

v1.3 problem: "Tester" sirf AST syntax + safety + keyword check karta tha --
unittest suites kabhi EXECUTE nahi hoti thi. Ab `run_suite()` real
execution deta hai (core/test_runner.py ke through), failures ke structured
tracebacks healer ko milte hain.

Static `test_code()` ab bhi fast pre-flight gate hai (execution se pehle).
"""

import ast
import sys
import os
from dataclasses import dataclass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from saleha.core.safety_patterns import check_dangerous


@dataclass
class TestResult:
    passed: bool
    error_message: str = ""
    error_type: str = "None"


class TesterAgent:
    """Code checker: static pre-flight (AST/safety/keywords) + REAL unittest
    execution via run_suite()."""

    def test_code(self, code: str, expected_keywords: list = None,
                  language: str = "python") -> TestResult:
        """
        कोड की सिंटैक्स, सुरक्षा, और अर्थपूर्ण (semantic) वैधता की जाँच करता है।
        C2: non-Python languages ke liye AST parse skip hota hai (valid JS ko
        SyntaxError flag karna galat hoga) -- safety regex sab pe lagti hai.
        """
        if not code or not code.strip():
            return TestResult(passed=False, error_message="कोड खाली है।", error_type="EmptyCode")

        # 1. Syntax Check (Python-only -- AST parser single-language hai)
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                return TestResult(
                    passed=False,
                    error_message=f"Syntax Error: लाइन {e.lineno}, {e.msg}",
                    error_type="SyntaxError"
                )

        # 2. Security Check (shared list, code_executor.py ke saath consistent)
        danger = check_dangerous(code)
        if danger:
            return TestResult(
                passed=False,
                error_message=f"Security Risk: {danger.description} (pattern: '{danger.pattern}')",
                error_type="SecurityViolation"
            )

        # 3. Semantic Check
        if expected_keywords:
            code_lower = code.lower()
            missing_keywords = [kw for kw in expected_keywords if kw.lower() not in code_lower]

            if missing_keywords:
                return TestResult(
                    passed=False,
                    error_message=f"Semantic Mismatch: कोड में ये आवश्यक कीवर्ड्स नहीं मिले: {missing_keywords}",
                    error_type="SemanticError"
                )

        return TestResult(passed=True, error_message="", error_type="None")

    def run_suite(self, code: str, test_code: str = None, timeout: int = 15,
                  expected_keywords: list = None):
        """REAL execution: static gate pass ho to unittest suite (ya bare
        smoke-test) sandbox me chalata hai.

        Returns core.test_runner.TestSuiteResult -- .passed / .failures /
        .failure_report() healer prompts ke liye.
        """
        from saleha.core.test_runner import TestRunner

        static = self.test_code(code, expected_keywords)
        if not static.passed:
            from saleha.core.test_runner import TestSuiteResult
            blocked = static.error_type == "SecurityViolation"
            return TestSuiteResult(
                passed=False, error=f"{static.error_type}: {static.error_message}",
                blocked=blocked,
            )

        runner = getattr(self, "_runner", None)
        if runner is None:
            runner = TestRunner()
            self._runner = runner
        if timeout is not None and hasattr(runner.executor, "timeout"):
            runner.executor.timeout = timeout
        return runner.run_suite(code, test_code=test_code)


if __name__ == "__main__":
    print("="*70)
    print("🧪 SALEHA TESTER AGENT - SHARED SAFETY PATTERNS TEST")
    print("="*70)

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
        result = tester.test_code(test['code'], test.get('keywords'))
        if result.passed:
            print("✅ PASSED")
        else:
            print(f"❌ FAILED: {result.error_type} - {result.error_message}")