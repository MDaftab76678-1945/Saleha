import unittest

from saleha.core.verification.oracle_check import differential_check, entry_point

ORACLE = "def lis_length(nums):\n" \
         "    from itertools import combinations\n" \
         "    best = 0\n" \
         "    for r in range(len(nums) + 1):\n" \
         "        for c in combinations(nums, r):\n" \
         "            if all(a < b for a, b in zip(c, c[1:])):\n" \
         "                best = max(best, r)\n" \
         "    return best\n"
FAST = "import bisect\ndef lis_length(nums):\n    t = []\n    for x in nums:\n" \
       "        i = bisect.bisect_left(t, x)\n        t[i:i + 1] = [x]\n    return len(t)\n"
BUGGY = "import bisect\ndef lis_length(nums):\n    t = []\n    for x in nums:\n" \
        "        i = bisect.bisect_right(t, x)\n        t[i:i + 1] = [x]\n    return len(t)\n"  # non-strict
GEN = "def gen(rng):\n    return ([rng.randint(0, 3) for _ in range(rng.randint(0, 7))],)\n"


class OracleCheckTests(unittest.TestCase):
    def test_correct_fast_solution_matches_brute_force(self) -> None:
        v = differential_check(FAST, ORACLE, GEN, "lis_length", n=150)
        self.assertTrue(v.supported, v.reason)
        self.assertEqual(v.checked, 150)

    def test_subtle_bug_is_caught(self) -> None:
        # bisect_right counts equal elements -- passes many hand tests, wrong on duplicates.
        v = differential_check(BUGGY, ORACLE, GEN, "lis_length", n=150)
        self.assertFalse(v.supported)
        self.assertIn("args=", v.mismatch)
        # An early mismatch must be reported as one, not as "too few inputs".
        self.assertEqual(v.reason, "differs from the brute-force oracle")

    def test_counterexample_is_shrunk_to_the_smallest_failing_input(self) -> None:
        # Seed 0 draws 6 items; the bug needs only two equal ones.
        wide = "def gen(rng):\n    return ([rng.randint(0, 3) for _ in range(rng.randint(5, 8))],)\n"
        v = differential_check(BUGGY, ORACLE, wide, "lis_length", n=50)
        self.assertRegex(v.mismatch, r"^args=\(\[(\d), \1\],\) oracle=\('ok', 1\) candidate=\('ok', 2\)$")
        self.assertRegex(v.first_mismatch, r"^args=\(\[\d(, \d){4,}\],\)")

    def test_shrinking_never_uses_an_input_the_oracle_rejects(self) -> None:
        # The oracle raises on lists shorter than 3; the shrunk input must keep 3.
        oracle = ORACLE.replace("    best = 0\n", "    if len(nums) < 3:\n        raise ValueError\n    best = 0\n")
        wide = "def gen(rng):\n    return ([rng.randint(0, 3) for _ in range(rng.randint(5, 8))],)\n"
        v = differential_check(BUGGY, oracle, wide, "lis_length", n=50)
        self.assertRegex(v.mismatch, r"^args=\(\[\d, \d, \d\],\)")

    def test_degenerate_generator_is_not_evidence(self) -> None:
        bad_gen = "def gen(rng):\n    return (None,)\n"
        v = differential_check(FAST, ORACLE, bad_gen, "lis_length", n=20)
        self.assertFalse(v.supported)
        self.assertIn("generator", v.reason)

    def test_generator_that_sometimes_crashes_is_tolerated(self) -> None:
        # Real 3B generators did `rng.randint(1, 0)` on some draws.
        flaky = ("def gen(rng):\n    n = rng.randint(0, 7)\n"
                 "    if n == 3:\n        raise ValueError('empty range')\n"
                 "    return ([rng.randint(0, 3) for _ in range(n)],)\n")
        v = differential_check(FAST, ORACLE, flaky, "lis_length", n=100)
        self.assertTrue(v.supported, v.reason)
        self.assertLess(v.checked, 100)

    def test_generator_that_always_crashes_is_not_evidence(self) -> None:
        v = differential_check(FAST, ORACLE, "def gen(rng):\n    raise ValueError\n", "lis_length", n=20)
        self.assertFalse(v.supported)
        self.assertIn("too few inputs", v.reason)

    def test_dangerous_code_is_refused(self) -> None:
        v = differential_check("import os\ndef lis_length(n):\n    return 0\n", ORACLE, GEN, "lis_length")
        self.assertFalse(v.supported)
        self.assertIn("safety", v.reason)

    def test_entry_point(self) -> None:
        self.assertEqual(entry_point("Write a Python function `edit_distance(a, b)` returning"), "edit_distance")
        self.assertIsNone(entry_point("Write a Python class `Trie` with `insert(word)`"))


class SwarmOracleTests(unittest.TestCase):
    """The swarm's QA stage asks for a brute-force version and compares."""

    GOAL = "Write `lis_length(nums)`: length of the longest strictly increasing subsequence"
    # Weak model-written suite: BUGGY passes it (no repeated values).
    WEAK_TESTS = ("import unittest\nclass T(unittest.TestCase):\n"
                  "    def test_basic(self):\n        self.assertEqual(lis_length([1, 3, 2, 4]), 3)\n")

    def _run(self, code: str, *later: str) -> tuple:
        from unittest.mock import patch

        from saleha.agents.coder import CodeResult
        from saleha.agents.qa_lead import QATestSuite
        from saleha.core.swarm.swarm_pipeline_engine import SwarmPipelineEngine
        from saleha.tests.swarm_stubs import stub_agents

        # solution, brute-force version, then generator(s) and any repair attempts
        outputs = iter([code, ORACLE, *(later or (GEN,))])
        suite = QATestSuite(task=self.GOAL, framework="unittest", test_code=self.WEAK_TESTS,
                            test_case_count=1, edge_cases_covered=[])
        with stub_agents(), \
             patch("saleha.agents.coder.CoderAgent.generate_code",
                   side_effect=lambda *a, **k: CodeResult(success=True, code=next(outputs))), \
             patch("saleha.agents.qa_lead.QALeadAgent.generate_test_suite", return_value=suite):
            res = SwarmPipelineEngine().execute_swarm(self.GOAL)
        return res, next(s for s in res.stages if s.agent_role == "QALead")

    def test_brute_force_catches_code_the_weak_tests_pass(self) -> None:
        res, qa = self._run(BUGGY, GEN, BUGGY, BUGGY, BUGGY)  # every repair returns the same bug
        self.assertFalse(res.tests_passed)
        self.assertFalse(res.success)
        self.assertIn("differs from a brute-force version", qa.output_summary)
        self.assertTrue(qa.payload["oracle"]["mismatch"])

    def test_correct_code_is_confirmed_by_brute_force(self) -> None:
        res, qa = self._run(FAST)
        self.assertTrue(res.tests_passed, qa.output_summary)
        self.assertTrue(qa.payload["oracle"]["supported"])
        self.assertIn("matches a brute-force version", qa.output_summary)

    def test_a_crashing_generator_is_replaced(self) -> None:
        crashing = "def gen(rng):\n    raise ValueError('bad draw')\n"
        res, qa = self._run(FAST, crashing, GEN)
        self.assertTrue(qa.payload["oracle"]["supported"], qa.payload["oracle"])
        self.assertEqual(qa.payload["oracle"]["generator_attempts"], 2)

    def test_counterexample_drives_a_rechecked_fix(self) -> None:
        res, qa = self._run(BUGGY, GEN, FAST)  # the one repair attempt returns the fix
        self.assertEqual(res.final_code, FAST)
        self.assertTrue(res.tests_passed, qa.output_summary)
        self.assertIn("after fixing its failure on", qa.output_summary)
        self.assertEqual(qa.payload["oracle"]["repair_attempts"], 1)

    def test_a_fix_that_still_differs_is_not_accepted(self) -> None:
        worse = "def lis_length(nums):\n    return len(nums)\n"
        res, qa = self._run(BUGGY, GEN, worse, BUGGY, BUGGY)
        self.assertFalse(res.success)
        self.assertNotEqual(res.final_code, worse)
        self.assertIn("differs from a brute-force version", qa.output_summary)


if __name__ == "__main__":
    unittest.main()
