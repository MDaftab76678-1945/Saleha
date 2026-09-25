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


if __name__ == "__main__":
    unittest.main()
