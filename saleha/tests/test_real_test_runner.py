"""
A1 Real Test Runner tests -- ye ACTUAL subprocess execution use karte hain
(koi LLM mock nahi): passing suite, failing assertions, errors, bare smoke,
__main__ guard stripping, aur static-gate short-circuit.
"""
import unittest

from saleha.agents.tester import TesterAgent
from saleha.core.harness.test_runner import (
    TestRunner,
    build_runner_script,
    sanitize_test_code,
)

PASSING_CODE = """
def add(a, b):
    return a + b
"""

PASSING_TESTS = """
import unittest

class TestAdd(unittest.TestCase):
    def test_positive(self) -> None:
        self.assertEqual(add(2, 3), 5)

    def test_negative(self) -> None:
        self.assertEqual(add(-1, -1), -2)
"""

FAILING_TESTS = """
import unittest

class TestAddBroken(unittest.TestCase):
    def test_wrong_expectation(self) -> None:
        self.assertEqual(add(2, 2), 5)
"""

ERRORING_TESTS = """
import unittest

class TestAddCrash(unittest.TestCase):
    def test_raises(self) -> None:
        raise ValueError("boom in test")
"""


class RunnerScriptTests(unittest.TestCase):
    def test_main_guard_is_stripped(self) -> None:
        tests = (
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self) -> None:\n"
            "        pass\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        cleaned = sanitize_test_code(tests)
        self.assertNotIn("unittest.main()", cleaned)
        self.assertIn("def test_ok", cleaned)

    def test_standalone_main_call_stripped(self) -> None:
        cleaned = sanitize_test_code("import unittest\nunittest.main()\n")
        self.assertNotIn("unittest.main(", cleaned)

    def test_script_contains_marker_and_exit_logic(self) -> None:
        script = build_runner_script(PASSING_CODE, PASSING_TESTS)
        self.assertIn("SALEHA_TEST_JSON:", script)
        self.assertIn("_sys.exit(0 if _result.wasSuccessful() else 1)", script)


class TestRunnerRealExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = TestRunner()

    def test_passing_suite_reports_success_and_count(self) -> None:
        res = self.runner.run_suite(PASSING_CODE, test_code=PASSING_TESTS, timeout=15)
        self.assertTrue(res.passed, msg=res.failure_report())
        self.assertGreaterEqual(res.ran, 2)
        self.assertEqual(res.failures, [])

    def test_failing_assertion_is_parsed_with_traceback(self) -> None:
        res = self.runner.run_suite(PASSING_CODE, test_code=FAILING_TESTS, timeout=15)
        self.assertFalse(res.passed)
        self.assertEqual(res.ran, 1)
        self.assertEqual(len(res.failures), 1)
        self.assertIn("test_wrong_expectation", res.failures[0].test_name)
        self.assertIn("AssertionError", res.failures[0].traceback)
        report = res.failure_report()
        self.assertIn("AssertionError", report)

    def test_erroring_test_counts_as_failure(self) -> None:
        combined = FAILING_TESTS + "\n" + ERRORING_TESTS
        res = self.runner.run_suite(PASSING_CODE, test_code=combined, timeout=15)
        self.assertFalse(res.passed)
        names = " ".join(f.test_name for f in res.failures)
        self.assertIn("test_wrong_expectation", names)
        self.assertIn("test_raises", names)
        self.assertIn("ValueError", res.failure_report())

    def test_solution_crash_before_tests_is_reported_as_error(self) -> None:
        bad_code = "raise RuntimeError('module import boom')\n"
        res = self.runner.run_suite(bad_code, test_code=PASSING_TESTS, timeout=15)
        self.assertFalse(res.passed)
        self.assertTrue(res.error or res.failures)

    def test_bare_smoke_mode_without_tests(self) -> None:
        ok = self.runner.run_suite("print('just running')\n", test_code=None, timeout=10)
        self.assertTrue(ok.passed)
        self.assertEqual(ok.ran, 0)  # no unittest ran

        crash = self.runner.run_suite("raise ValueError('nope')\n", test_code=None, timeout=10)
        self.assertFalse(crash.passed)
        self.assertIn("ValueError", (crash.error or "") + crash.raw_output)

    def test_blocked_import_short_circuits_via_static_gate(self) -> None:
        tester = TesterAgent()
        res = tester.run_suite("import socket\nprint(socket)\n", test_code=None, timeout=10)
        self.assertFalse(res.passed)
        self.assertTrue(res.blocked)
        self.assertIn("Blocked", res.error)

    def test_test_code_with_zero_test_methods_is_not_a_pass(self) -> None:
        # test_code was supplied but contributes no runnable test method (comments
        # only, or a malformed/non-TestCase class) -- nothing was verified, so this
        # must not be reported as passed. Regression for a fabricated-green bug: the
        # old code returned passed=True/ran=0 here, indistinguishable from a real
        # suite that genuinely proved the solution correct.
        res = self.runner.run_suite(PASSING_CODE, test_code="# no tests written yet\n", timeout=15)
        self.assertFalse(res.passed)
        self.assertEqual(res.ran, 0)
        self.assertIn("0 tests", res.error)

    def test_testeragent_run_suite_end_to_end(self) -> None:
        tester = TesterAgent()
        res = tester.run_suite(PASSING_CODE, test_code=PASSING_TESTS, timeout=15)
        self.assertTrue(res.passed)
        # Static gate short circuit: syntax error code ko execute kiye bina fail
        res2 = tester.run_suite("def broken(:\n", test_code=PASSING_TESTS, timeout=10)
        self.assertFalse(res2.passed)
        self.assertTrue(res2.error)  # SyntaxError from static gate, no execution


if __name__ == "__main__":
    unittest.main()
