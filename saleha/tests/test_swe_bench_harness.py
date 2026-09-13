"""Unit tests for the sandbox self-check.

These replace tests that asserted `pass_rate == 100.0` on both the executed
and the `dry_run` path. That was the recurring trap CLAUDE.md describes: the
old `dry_run` hardcoded `resolved = True` without executing anything, so the
test passed precisely because the code was fabricating, and would have kept
passing no matter how broken the executor became.
"""

import unittest
from saleha.core.swe_bench_harness import SandboxSelfCheck, SWEBenchTask


GOOD = SWEBenchTask(
    instance_id="SELFCHECK-OK",
    repo="saleha/core",
    problem_statement="Known-good code that prints the marker.",
    base_code="def fix_me(): return 42\n",
    test_patch="assert fix_me() == 42\nprint('SWE_BENCH_VERIFIED')",
)

BROKEN = SWEBenchTask(
    instance_id="SELFCHECK-BROKEN",
    repo="saleha/core",
    problem_statement="Code whose assertion fails, so the marker never prints.",
    base_code="def fix_me(): return 0\n",
    test_patch="assert fix_me() == 42\nprint('SWE_BENCH_VERIFIED')",
)


class SandboxSelfCheckTests(unittest.TestCase):

    def test_known_good_code_executes_cleanly(self):
        report = SandboxSelfCheck(tasks=[GOOD]).run_self_check()
        self.assertTrue(report.did_execute)
        self.assertEqual(report.executed_ok, 1)
        self.assertTrue(report.results[0]["executed_ok"])

    def test_failing_code_is_reported_as_failing(self):
        # The old harness could not produce this outcome for any input on the
        # dry_run path, which is what made its 100% meaningless.
        report = SandboxSelfCheck(tasks=[BROKEN]).run_self_check()
        self.assertTrue(report.did_execute)
        self.assertEqual(report.executed_ok, 0)
        self.assertFalse(report.results[0]["executed_ok"])

    def test_list_only_claims_no_result(self):
        report = SandboxSelfCheck(tasks=[GOOD]).run_self_check(list_only=True)
        self.assertFalse(report.did_execute)
        self.assertEqual(report.executed_ok, 0)
        self.assertIsNone(report.results[0]["executed_ok"])

    def test_list_only_markdown_says_nothing_ran(self):
        md = SandboxSelfCheck(tasks=[GOOD]).run_self_check(list_only=True).render_markdown()
        self.assertIn("NOT RUN", md)
        self.assertNotIn("Leaderboard", md)

    def test_markdown_does_not_claim_a_benchmark(self):
        md = SandboxSelfCheck(tasks=[GOOD]).run_self_check().render_markdown()
        self.assertIn("not a capability measurement", md)
        self.assertNotIn("Pass@1", md)


if __name__ == "__main__":
    unittest.main()

