import unittest

from saleha.core.verification.cross_check import cross_check

GOOD_A = "def is_pal(s):\n    t = ''.join(c for c in s.lower() if c.isalnum())\n    return t == t[::-1]\n"
GOOD_B = "def is_pal(s):\n    t = [c for c in s.lower() if c.isalnum()]\n    return t == list(reversed(t))\n"
WRONG = "def is_pal(s):\n    return s == s[::-1]\n"  # case-sensitive

GOOD_TESTS = ("import unittest\nclass T(unittest.TestCase):\n"
              "    def test_mixed(self):\n        self.assertTrue(is_pal('Aba'))\n"
              "    def test_no(self):\n        self.assertFalse(is_pal('abc'))\n")
# The real-run mistake: contradicts "ignores case".
WRONG_TEST = ("import unittest\nclass W(unittest.TestCase):\n"
              "    def test_upper(self):\n        self.assertFalse(is_pal('A'))\n")


class CrossCheckTests(unittest.TestCase):
    def test_agreeing_correct_candidates_win_despite_a_wrong_test(self) -> None:
        res = cross_check([WRONG, GOOD_A, GOOD_B], [GOOD_TESTS, WRONG_TEST])
        self.assertIn(res.winner_index, (1, 2))
        self.assertEqual(sorted(res.group), [1, 2])
        self.assertIn("2/3", res.agreement)

    def test_one_candidate_is_not_cross_checked(self) -> None:
        res = cross_check([GOOD_A], [GOOD_TESTS])
        self.assertIsNone(res.winner_index)
        self.assertIn("at least 2", res.reason)

    def test_identical_copies_are_not_independent_agreement(self) -> None:
        res = cross_check([GOOD_A, GOOD_A + "\n"], [GOOD_TESTS])
        self.assertIsNone(res.winner_index)
        self.assertEqual(res.candidates, 1)

    def test_swarm_uses_agreement_not_one_wrong_suite(self) -> None:
        from unittest.mock import patch

        from saleha.agents.coder import CodeResult
        from saleha.agents.qa_lead import QATestSuite
        from saleha.core.swarm.swarm_pipeline_engine import SwarmPipelineEngine
        from saleha.tests.swarm_stubs import stub_agents

        codes = iter([GOOD_A, WRONG, GOOD_B])
        suites = iter([WRONG_TEST, GOOD_TESTS])

        def fake_suite(task: str, _code: str, framework: str = "unittest") -> QATestSuite:
            return QATestSuite(task=task, framework="unittest", test_code=next(suites),
                               test_case_count=1, edge_cases_covered=[])

        with stub_agents(), \
             patch("saleha.agents.coder.CoderAgent.generate_code",
                   side_effect=lambda *a, **k: CodeResult(success=True, code=next(codes))), \
             patch("saleha.agents.qa_lead.QALeadAgent.generate_test_suite", side_effect=fake_suite):
            res = SwarmPipelineEngine(candidates=3).execute_swarm("palindrome ignoring case")
        qa = next(s for s in res.stages if s.agent_role == "QALead")
        # One suite alone (the wrong one) would fail GOOD_A; agreement passes it.
        self.assertTrue(res.success, qa.output_summary)
        self.assertIn(res.final_code, (GOOD_A, GOOD_B))
        self.assertIn("2/3", qa.payload["agreement"])

    def test_no_passing_test_means_no_winner(self) -> None:
        broken = "def is_pal(s):\n    raise NotImplementedError\n"
        res = cross_check([broken, broken], [GOOD_TESTS])
        self.assertIsNone(res.winner_index)


if __name__ == "__main__":
    unittest.main()
