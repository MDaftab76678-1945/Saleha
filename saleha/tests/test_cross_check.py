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

    def test_no_passing_test_means_no_winner(self) -> None:
        broken = "def is_pal(s):\n    raise NotImplementedError\n"
        res = cross_check([broken, broken], [GOOD_TESTS])
        self.assertIsNone(res.winner_index)


if __name__ == "__main__":
    unittest.main()
