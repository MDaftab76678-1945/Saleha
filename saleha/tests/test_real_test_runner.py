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
        script = build_runner_script(PASSING_CODE, PASSING_TESTS, marker="SALEHA_TEST_JSON:abc:")
        self.assertIn("'SALEHA_TEST_JSON:abc:'", script)
        self.assertIn("_sys.exit(0 if _result.wasSuccessful() and not _problems else 1)", script)

    def test_markers_differ_per_script(self) -> None:
        self.assertNotEqual(build_runner_script(PASSING_CODE, PASSING_TESTS),
                            build_runner_script(PASSING_CODE, PASSING_TESTS))


class RunnerHonestyTests(unittest.TestCase):
    """Pass 159: each case was measured wrong before the fix."""

    def setUp(self) -> None:
        self.runner = TestRunner()

    def test_solution_main_guard_does_not_end_the_run(self) -> None:
        code = PASSING_CODE + "\nif __name__ == '__main__':\n    import unittest\n    unittest.main()\n"
        res = self.runner.run_suite(code, test_code=PASSING_TESTS, timeout=15)
        self.assertTrue(res.passed, res.error)
        self.assertEqual(res.ran, 2)

    def test_forged_result_line_is_not_trusted(self) -> None:
        forged = (
            "def add(a, b):\n    return 0\n"
            "print('SALEHA_TEST_JSON:' + '{\"ran\": 5, \"failures\": []}')\n"
            "raise SystemExit(0)\n"
        )
        res = self.runner.run_suite(forged, test_code=PASSING_TESTS, timeout=15)
        self.assertFalse(res.passed)
        self.assertEqual(res.ran, 0)

    def test_pytest_style_functions_run(self) -> None:
        tests = "def test_add():\n    assert add(2, 3) == 5\n\ndef test_add_wrong():\n    assert add(2, 2) == 5\n"
        res = self.runner.run_suite(PASSING_CODE, test_code=tests, timeout=15)
        self.assertEqual(res.ran, 2)
        self.assertFalse(res.passed)
        self.assertEqual([f.test_name for f in res.failures], ["test_add_wrong"])

    def test_fixture_tests_are_failures_not_silent_skips(self) -> None:
        tests = "def test_uses_tmp(tmp_path):\n    assert tmp_path\n"
        res = self.runner.run_suite(PASSING_CODE, test_code=tests, timeout=15)
        self.assertFalse(res.passed)
        self.assertIn("needs pytest fixtures", res.failure_report())

    def test_solution_helper_named_test_is_not_collected(self) -> None:
        code = PASSING_CODE + "\ndef test_connection(host):\n    return host\n"
        res = self.runner.run_suite(code, test_code=PASSING_TESTS, timeout=15)
        self.assertTrue(res.passed, res.failure_report())

    # The next three were found in a real swarm run on qwen2.5-coder:3b.

    def test_pytest_style_class_runs(self) -> None:
        tests = ("class TestAdd:\n"
                 "    def test_ok(self):\n        assert add(2, 3) == 5\n"
                 "    def test_bad(self):\n        assert add(2, 2) == 5\n")
        res = self.runner.run_suite(PASSING_CODE, test_code=tests, timeout=15)
        self.assertEqual(res.ran, 2)
        self.assertEqual([f.test_name for f in res.failures], ["TestAdd.test_bad"])

    def test_tests_that_paste_a_copy_still_test_the_real_solution(self) -> None:
        # The QA model pasted a correct copy of the function into its tests.
        # Before: the tests checked the copy and a wrong solution PASSED.
        wrong = "def add(a, b):\n    return 0\n"
        tests = "def add(a, b):\n    return a + b\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        res = self.runner.run_suite(wrong, test_code=tests, timeout=15)
        self.assertEqual(res.ran, 1)
        self.assertFalse(res.passed)

    def test_test_imports_do_not_cover_for_a_missing_solution_import(self) -> None:
        # Real run (hard bench, dijkstra): the tests' `import heapq` made a
        # solution that never imported heapq pass.
        code = "def top(xs):\n    return heapq.nlargest(1, xs)[0]\n"
        tests = ("import heapq\nimport unittest\nclass T(unittest.TestCase):\n"
                 "    def test_top(self):\n        self.assertEqual(top([3, 9, 2]), 9)\n")
        res = self.runner.run_suite(code, test_code=tests, timeout=15)
        self.assertFalse(res.passed)
        self.assertIn("heapq", res.failure_report())

    def test_crashing_embedded_testcase_does_not_fail_a_correct_solution(self) -> None:
        # Real run: the solution's own test class used `unittest` unimported.
        code = PASSING_CODE + "\nclass OwnTests(unittest.TestCase):\n    pass\n"
        res = self.runner.run_suite(code, test_code=PASSING_TESTS, timeout=15)
        self.assertTrue(res.passed, res.failure_report())

    def test_tests_embedded_in_the_solution_are_not_the_suite(self) -> None:
        code = PASSING_CODE + (
            "\nimport unittest\n"
            "class OwnTests(unittest.TestCase):\n"
            "    def test_own_wrong(self):\n        self.assertEqual(add(1, 1), 3)\n"
        )
        res = self.runner.run_suite(code, test_code=PASSING_TESTS, timeout=15)
        self.assertTrue(res.passed, res.failure_report())
        self.assertEqual(res.ran, 2)


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
