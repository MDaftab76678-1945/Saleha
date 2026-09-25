"""Unit tests for the Saleha Harness.

Several of these replace tests that pinned fabricated behaviour: the dry-run
test used to assert `overall_pass_at_1 == 100.0` and, through the global
reporter, appended that 100% to the real ~/.saleha/harness_history.json on
every suite run -- which is how the leaderboard came to hold 947 dry-run
records and not one real evaluation.
"""

import importlib
import io
import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from click.testing import CliRunner
from rich.console import Console

from saleha.cli.commands import cli
from saleha.harness import core as harness_core
from saleha.harness.benchmarks import BenchmarkCatalog
from saleha.harness.core import SalehaHarness
from saleha.harness.metrics import HarnessTaskResult, compute_benchmark_summary, estimate_pass_at_k
from saleha.harness.reporter import BenchmarkSummary, HarnessReport, HarnessReporter

# `saleha.harness.reporter` the attribute is the HarnessReporter instance the
# package re-exports, not the module; fetch the module itself to patch it.
reporter_module = importlib.import_module("saleha.harness.reporter")

GOOD_BINARY_SEARCH = (
    "def binary_search(nums, target):\n"
    "    lo, hi = 0, len(nums) - 1\n"
    "    while lo <= hi:\n"
    "        mid = (lo + hi) // 2\n"
    "        if nums[mid] == target:\n"
    "            return mid\n"
    "        if nums[mid] < target:\n"
    "            lo = mid + 1\n"
    "        else:\n"
    "            hi = mid - 1\n"
    "    return -1\n"
)


def _orch_result(code: str, attempts: int = 1, profile_used: str = "", log: str = "") -> SimpleNamespace:
    return SimpleNamespace(final_code=code, attempts=attempts, profile_used=profile_used, log=log)


def _task(task_id: str):
    return next(t for t in BenchmarkCatalog.get_benchmarks("all") if t.id == task_id)


class SalehaHarnessTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_harness_test_")
        self.history_file = os.path.join(self.temp_dir, "test_harness_history.json")
        self.reporter = HarnessReporter(history_path=self.history_file)
        self.harness = SalehaHarness()
        # evaluate() saves through the module-level reporter; point it at the
        # temp file so no test can write the user's real leaderboard.
        patcher = mock.patch.object(harness_core, "reporter", self.reporter)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_with_code(self, task_id: str, orch: SimpleNamespace) -> HarnessTaskResult:
        with mock.patch.object(harness_core, "SalehaOrchestrator") as orch_cls:
            orch_cls.return_value.execute_task.return_value = orch
            return self.harness._evaluate_single_task(_task(task_id), "test-model")

    def test_unbiased_pass_at_k_calculation(self) -> None:
        self.assertEqual(estimate_pass_at_k(10, 10, k=1), 1.0)
        self.assertEqual(estimate_pass_at_k(10, 10, k=5), 1.0)
        self.assertEqual(estimate_pass_at_k(10, 0, k=1), 0.0)
        self.assertEqual(estimate_pass_at_k(10, 5, k=1), 0.5)
        self.assertEqual(estimate_pass_at_k(0, 0, k=1), 0.0)
        self.assertEqual(estimate_pass_at_k(5, 2, k=10), 0.0)

    def test_benchmark_catalog_retrieval(self) -> None:
        catalogs = BenchmarkCatalog.list_available_benchmarks()
        for name in ("humaneval_plus", "mbpp_plus", "math_reasoning", "swe_repo", "tool_use"):
            self.assertIn(name, catalogs)
        self.assertTrue(len(BenchmarkCatalog.get_benchmarks("all")) >= 9)

    def test_dry_run_has_no_score_and_is_not_saved(self) -> None:
        with mock.patch.object(harness_core, "SalehaOrchestrator") as orch_cls:
            report = self.harness.evaluate(model="mock-qwen-coder", benchmark="all", dry_run=True)
        orch_cls.assert_not_called()
        self.assertTrue(report.dry_run)
        self.assertIsNone(report.overall_pass_at_1)
        self.assertEqual(report.executed_tasks, 0)
        self.assertEqual(report.passed_tasks, 0)
        self.assertEqual(sum(len(v) for v in report.planned_tasks.values()), report.total_tasks)
        self.assertFalse(report.saved)
        self.assertFalse(os.path.exists(self.history_file))

    def test_forged_pass_marker_does_not_pass(self) -> None:
        # No binary_search defined; prints the old fixed marker and exits
        # before the task's assertions can run.
        forged = "print('HARNESS_TEST_PASSED')\nraise SystemExit(0)\n"
        res = self._run_with_code("HE-003-BINARY-SEARCH", _orch_result(forged))
        self.assertTrue(res.executed)
        self.assertFalse(res.passed)

    def test_correct_solution_passes(self) -> None:
        res = self._run_with_code("HE-003-BINARY-SEARCH", _orch_result(GOOD_BINARY_SEARCH))
        self.assertTrue(res.executed)
        self.assertTrue(res.passed, res.error_detail)

    def test_candidate_main_guard_does_not_decide_the_result(self) -> None:
        # The orchestrator's real output shape: a correct function followed by
        # its own unittest.main() under the __main__ guard. Before the fix this
        # exited before the task's tests ran and every task scored FAIL.
        own_tests = (
            "\nimport unittest\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_own(self):\n"
            "        self.assertEqual(binary_search([1], 1), 99)  # model's own wrong expectation\n\n"
            "if __name__ == \"__main__\":\n"
            "    unittest.main()\n"
        )
        res = self._run_with_code("HE-003-BINARY-SEARCH", _orch_result(GOOD_BINARY_SEARCH + own_tests))
        self.assertTrue(res.executed)
        self.assertTrue(res.passed, res.error_detail)

        wrong = "def binary_search(nums, target):\n    return 0\n" + own_tests
        res_wrong = self._run_with_code("HE-003-BINARY-SEARCH", _orch_result(wrong))
        self.assertFalse(res_wrong.passed)
        self.assertIn("AssertionError", res_wrong.error_detail or "")

    def test_strip_main_guard_leaves_other_code_intact(self) -> None:
        code = "x = 1\nif __name__ == '__main__':\n    print('main')\nif x:\n    y = 2\n"
        stripped = harness_core.strip_main_guard(code)
        self.assertNotIn("print('main')", stripped)
        self.assertIn("if x:\n    y = 2", stripped)
        self.assertEqual(stripped.splitlines()[0], "x = 1")
        self.assertEqual(harness_core.strip_main_guard("def f(:\n"), "def f(:\n")

    def test_wrong_solution_fails_with_reason(self) -> None:
        wrong = "def binary_search(nums, target):\n    return 0\n"
        res = self._run_with_code("HE-003-BINARY-SEARCH", _orch_result(wrong))
        self.assertTrue(res.executed)
        self.assertFalse(res.passed)
        self.assertIn("AssertionError", res.error_detail or "")

    def test_memory_replay_is_not_run(self) -> None:
        res = self._run_with_code("HE-003-BINARY-SEARCH",
                                  _orch_result(GOOD_BINARY_SEARCH, attempts=0, profile_used="memory_store"))
        self.assertFalse(res.executed)
        self.assertFalse(res.passed)
        self.assertIn("memory", res.error_detail or "")

    def test_harness_asks_orchestrator_to_skip_memory(self) -> None:
        with mock.patch.object(harness_core, "SalehaOrchestrator") as orch_cls:
            orch_cls.return_value.execute_task.return_value = _orch_result(GOOD_BINARY_SEARCH)
            self.harness._evaluate_single_task(_task("HE-003-BINARY-SEARCH"), "m")
        self.assertIs(orch_cls.return_value.execute_task.call_args.kwargs.get("use_memory"), False)

    def test_orchestrator_use_memory_false_skips_recall(self) -> None:
        from saleha import orchestrator as orch_module
        orch = orch_module.SalehaOrchestrator(model="m")
        cached = SimpleNamespace(code="def f(): return 1", hit_count=3, model="m", source_type="verified_execution")
        stop = RuntimeError("reached the planner")
        with mock.patch.object(orch_module.memory_store, "recall", return_value=cached) as recall, \
             mock.patch.object(orch_module.skill_registry, "find_skill", return_value=None), \
             mock.patch.object(orch.planner, "create_plan", side_effect=stop):
            with self.assertRaises(RuntimeError):
                orch.execute_task("write f", use_memory=False)
            recall.assert_not_called()
            replayed = orch.execute_task("write f")
        self.assertEqual(replayed.profile_used, "memory_store")

    def test_no_code_is_not_run(self) -> None:
        res = self._run_with_code("HE-003-BINARY-SEARCH",
                                  _orch_result("", attempts=0, log="Goal: x\nPlanning failed: model unreachable"))
        self.assertFalse(res.executed)
        self.assertIn("Planning failed: model unreachable", res.error_detail or "")

    def test_orchestrator_crash_is_not_run(self) -> None:
        with mock.patch.object(harness_core, "SalehaOrchestrator", side_effect=RuntimeError("boom")):
            res = self.harness._evaluate_single_task(_task("HE-003-BINARY-SEARCH"), "m")
        self.assertFalse(res.executed)
        self.assertIn("boom", res.error_detail or "")

    def test_run_where_nothing_executed_is_not_saved(self) -> None:
        with mock.patch.object(harness_core, "SalehaOrchestrator") as orch_cls:
            orch_cls.return_value.execute_task.return_value = _orch_result("", attempts=0, log="no model")
            report = self.harness.evaluate(model="m", benchmark="mbpp_plus", workers=1)
        self.assertEqual(report.executed_tasks, 0)
        self.assertIsNone(report.overall_pass_at_1)
        self.assertFalse(report.saved)
        self.assertFalse(os.path.exists(self.history_file))

    def test_real_run_is_saved_with_pass_rate_over_executed(self) -> None:
        with mock.patch.object(harness_core, "SalehaOrchestrator") as orch_cls:
            orch_cls.return_value.execute_task.return_value = _orch_result(GOOD_BINARY_SEARCH)
            report = self.harness.evaluate(model="m", benchmark="humaneval_plus", workers=1)
        # Only HE-003 is solved by this code; the other two fail on NameError.
        self.assertEqual((report.executed_tasks, report.passed_tasks), (3, 1))
        self.assertEqual(report.overall_pass_at_1, 33.33)
        self.assertTrue(report.saved)
        history = self.reporter.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["pass_at_1"], 33.33)
        self.assertNotIn("pass_at_5", history[0])

    def test_unknown_benchmark_and_bad_limit_raise(self) -> None:
        with self.assertRaises(ValueError):
            self.harness.evaluate(benchmark="no_such_suite", dry_run=True)
        with self.assertRaises(ValueError):
            self.harness.evaluate(benchmark="all", limit=0, dry_run=True)

    def test_summary_of_nothing_executed_is_none_not_zero(self) -> None:
        results = [HarnessTaskResult(task_id="t", benchmark="b", prompt="p", passed=False, executed=False)]
        summ = compute_benchmark_summary("b", results)
        self.assertIsNone(summ.pass_at_1)
        self.assertEqual((summ.total_tasks, summ.executed_tasks), (1, 0))

    def test_reporter_refuses_dry_run(self) -> None:
        report = HarnessReport(model_name="m", timestamp="t", total_tasks=3, executed_tasks=0,
                               passed_tasks=0, overall_pass_at_1=None, avg_latency_sec=0.0, dry_run=True)
        self.assertFalse(self.reporter.save_report(report))
        self.assertFalse(os.path.exists(self.history_file))

    def test_corrupt_history_is_preserved_not_overwritten(self) -> None:
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write("{not json")
        report = HarnessReport(model_name="m", timestamp="t", total_tasks=1, executed_tasks=1,
                               passed_tasks=1, overall_pass_at_1=100.0, avg_latency_sec=0.1)
        self.assertTrue(self.reporter.save_report(report))
        backups = [n for n in os.listdir(self.temp_dir) if ".corrupt-" in n]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.temp_dir, backups[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), "{not json")
        self.assertEqual(len(self.reporter.load_history()), 1)

    def test_leaderboard_renders_on_cp1252(self) -> None:
        report = HarnessReport(model_name="qwen2.5-coder:3b", timestamp="2026-09-25 10:00:00",
                               total_tasks=9, executed_tasks=8, passed_tasks=6,
                               overall_pass_at_1=75.0, avg_latency_sec=2.5)
        self.assertTrue(self.reporter.save_report(report))
        # A cp1252 stream, like this machine's console: Rich falls back to
        # ASCII box drawing, and any emoji raises UnicodeEncodeError on write.
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252")
        with mock.patch.object(reporter_module, "console", Console(file=stream, width=200)):
            self.reporter.render_leaderboard()
        stream.flush()
        out = raw.getvalue().decode("cp1252")
        self.assertIn("75.0%", out)
        self.assertIn("6 / 8", out)

    def test_reporter_export_markdown(self) -> None:
        report = HarnessReport(
            model_name="qwen2.5-coder:3b", timestamp="2026-08-24 22:00:00",
            total_tasks=3, executed_tasks=2, passed_tasks=1, overall_pass_at_1=50.0, avg_latency_sec=0.25,
            benchmark_summaries={"humaneval_plus": BenchmarkSummary(
                benchmark_name="humaneval_plus", total_tasks=3, passed_tasks=1, executed_tasks=2, pass_at_1=50.0,
                task_results=[
                    HarnessTaskResult(task_id="A", benchmark="humaneval_plus", prompt="p", passed=True),
                    HarnessTaskResult(task_id="B", benchmark="humaneval_plus", prompt="p", passed=False,
                                      error_detail="Traceback (most recent call last):\n  File x\nKeyError: 'params'\n"),
                    HarnessTaskResult(task_id="C", benchmark="humaneval_plus", prompt="p", passed=False,
                                      executed=False, error_detail="replayed from memory store"),
                ])},
        )
        export_file = os.path.join(self.temp_dir, "report.md")
        self.assertTrue(self.reporter.export_markdown(report, export_file))
        with open(export_file, encoding="utf-8") as f:
            text = f.read()
        text.encode("cp1252")
        self.assertIn("PASS **[A]**", text)
        self.assertIn("FAIL **[B]** (Latency: 0.0s, Attempts: 1) -- KeyError: 'params'", text)
        self.assertIn("NOT RUN **[C]**", text)

    def test_cli_harness_commands(self) -> None:
        runner = CliRunner()

        res_list = runner.invoke(cli, ["harness", "list", "--json"])
        self.assertEqual(res_list.exit_code, 0)

        res_run = runner.invoke(cli, ["harness", "run", "--benchmark", "mbpp_plus", "--dry-run", "--json"])
        self.assertEqual(res_run.exit_code, 0, res_run.output)
        payload = json.loads(res_run.output)
        self.assertTrue(payload["dry_run"])
        self.assertIsNone(payload["overall_pass_at_1"])
        self.assertFalse(payload["saved_to_history"])
        self.assertFalse(os.path.exists(self.history_file))

        res_bad = runner.invoke(cli, ["harness", "run", "--benchmark", "nope", "--dry-run"])
        self.assertNotEqual(res_bad.exit_code, 0)
        self.assertIn("unknown benchmark", res_bad.output)


if __name__ == "__main__":
    unittest.main()
