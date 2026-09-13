"""Tests for the local task benchmark runner and the benchmark reporter.

The previous version of this file pinned a fabrication in place. It asserted:

    def test_all_builtin_tasks_solvable(self):
        run = self.leaderboard.run_suite(use_llm=False)
        self.assertEqual(run.solved, len(BUILTIN_TASKS))
        self.assertEqual(run.score_pct, 100.0)

That passed for one reason: `_generate_fix()` returned `task["expected_fix"]`
-- the answer key -- and `_evaluate_fix()` then executed the answer key
against the task's own test. A 100% that could never be anything else, and a
test that would have kept passing however broken the real pipeline became.

These tests assert the properties that make a benchmark mean something: that
a wrong answer scores zero, that the suite refuses to run when a test cannot
fail, and that an unreachable model is reported as a failure rather than a
default.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest import mock

from saleha.core.benchmark_reporter import (
    PUBLIC_SWEBENCH_VERIFIED_REFERENCE,
    BenchmarkReporter,
)
from saleha.core.real_task_bench import (
    TASKS,
    Task,
    extract_code,
    run_benchmark,
    run_in_subprocess,
    verify_tests_can_fail,
)
from saleha.core.swe_leaderboard import LocalTaskBenchmark


class TestsMustBeAbleToFail(unittest.TestCase):
    """The gate the fabricated harness did not have."""

    def test_every_shipped_task_fails_on_wrong_code(self) -> None:
        # If this ever fails, the affected task's test passes for any output
        # and its contribution to the score is meaningless.
        self.assertEqual(verify_tests_can_fail(), [])

    def test_a_test_that_cannot_fail_is_reported(self) -> None:
        cannot_fail = Task(
            task_id="always_passes",
            prompt="anything",
            test="assert True\n",
            wrong_impl="x = 1\n",
        )
        self.assertEqual(verify_tests_can_fail([cannot_fail]), ["always_passes"])

    def test_run_refuses_to_start_when_a_test_cannot_fail(self) -> None:
        cannot_fail = Task("always_passes", "anything", "assert True\n", "x = 1\n")
        report = run_benchmark(model="unused", tasks=[cannot_fail])
        self.assertFalse(report.did_run)
        self.assertEqual(report.pass_rate, 0.0)
        self.assertIn("cannot measure anything", report.refused_reason)


class RealScoringTests(unittest.TestCase):

    def test_correct_code_passes_and_wrong_code_fails(self) -> None:
        task = next(t for t in TASKS if t.task_id == "safe_divide")
        correct = ("def safe_divide(a, b):\n"
                   "    return None if b == 0 else a / b\n")
        ok_right, _ = run_in_subprocess(correct, task.test)
        ok_wrong, err = run_in_subprocess(task.wrong_impl, task.test)
        self.assertTrue(ok_right)
        self.assertFalse(ok_wrong)
        self.assertTrue(err)

    def test_model_returning_wrong_code_scores_zero(self) -> None:
        task = next(t for t in TASKS if t.task_id == "safe_divide")
        with mock.patch("saleha.core.real_task_bench.generate",
                        return_value="```python\ndef safe_divide(a, b):\n    return a / b\n```"):
            report = run_benchmark(model="fake", tasks=[task])
        self.assertTrue(report.did_run)
        self.assertEqual(report.passed, 0)
        self.assertEqual(report.pass_rate, 0.0)
        self.assertTrue(report.outcomes[0].error)

    def test_model_returning_correct_code_scores_one(self) -> None:
        task = next(t for t in TASKS if t.task_id == "safe_divide")
        with mock.patch("saleha.core.real_task_bench.generate",
                        return_value="```python\ndef safe_divide(a, b):\n"
                                     "    return None if b == 0 else a / b\n```"):
            report = run_benchmark(model="fake", tasks=[task])
        self.assertEqual(report.passed, 1)
        self.assertEqual(report.pass_rate, 100.0)

    def test_unreachable_model_is_a_failure_not_a_default(self) -> None:
        task = next(t for t in TASKS if t.task_id == "safe_divide")
        with mock.patch("saleha.core.real_task_bench.generate",
                        side_effect=OSError("connection refused")):
            report = run_benchmark(model="fake", tasks=[task])
        self.assertTrue(report.did_run)
        self.assertEqual(report.passed, 0)
        self.assertIn("model call failed", report.outcomes[0].error)

    def test_model_own_demo_code_is_stripped_before_execution(self) -> None:
        # A model appending its own (wrong) test used to fail a correct answer.
        reply = ("```python\n"
                 "def safe_divide(a, b):\n"
                 "    return None if b == 0 else a / b\n"
                 "\n"
                 "assert safe_divide(1, 0) == 0    # the model's own wrong test\n"
                 "print('demo')\n"
                 "```")
        code = extract_code(reply)
        self.assertIn("def safe_divide", code)
        self.assertNotIn("print(", code)
        self.assertNotIn("assert", code)


class LocalTaskBenchmarkTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.reporter = BenchmarkReporter(
            scores_path=os.path.join(self.tmp, "scores.jsonl"))
        self.bench = LocalTaskBenchmark(reporter=self.reporter)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_preflight_reports_the_suite_is_usable(self) -> None:
        pre = self.bench.preflight()
        self.assertEqual(pre["total_tasks"], len(TASKS))
        self.assertEqual(pre["tests_that_cannot_fail"], [])
        self.assertTrue(pre["usable"])

    def test_run_records_the_real_score_not_a_default(self) -> None:
        task = next(t for t in TASKS if t.task_id == "safe_divide")
        with mock.patch("saleha.core.real_task_bench.TASKS", [task]), \
             mock.patch("saleha.core.real_task_bench.generate",
                        return_value="```python\ndef safe_divide(a, b):\n    return a / b\n```"):
            run = self.bench.run_suite(model="fake")
        self.assertEqual(run.suite, "local_tasks")
        self.assertEqual(run.solved, 0)
        self.assertEqual(run.score_pct, 0.0)
        # The label names the suite that ran and disclaims the one that did
        # not: "saleha local_tasks (not SWE-bench)".
        self.assertIn("local_tasks", run.metadata["benchmark"])
        self.assertIn("not SWE-bench", run.metadata["benchmark"])

    def test_task_results_carry_the_real_generated_code(self) -> None:
        task = next(t for t in TASKS if t.task_id == "safe_divide")
        good = "```python\ndef safe_divide(a, b):\n    return None if b == 0 else a / b\n```"
        with mock.patch("saleha.core.real_task_bench.TASKS", [task]), \
             mock.patch("saleha.core.real_task_bench.generate", return_value=good):
            run = self.bench.run_suite(model="fake")
        results = self.bench.task_results(run)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].solved)
        self.assertIn("def safe_divide", results[0].fix_applied)

    def test_leaderboard_text_does_not_rank_us_against_swebench(self) -> None:
        text = self.bench.leaderboard_text()
        self.assertIn("has NOT run", text)
        self.assertIn("not comparable", text)
        self.assertNotIn("← YOU", text)


class PublicReferenceTests(unittest.TestCase):

    def test_reference_figures_are_labelled_as_another_benchmark(self) -> None:
        self.assertIn("Devin (Cognition)", PUBLIC_SWEBENCH_VERIFIED_REFERENCE)
        self.assertGreater(PUBLIC_SWEBENCH_VERIFIED_REFERENCE["Devin (Cognition)"], 0)


if __name__ == "__main__":
    unittest.main()
