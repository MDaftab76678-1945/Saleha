"""Unit tests for Gödel Machine Self-Proving Utility Engine."""

import unittest
from saleha.core.godel_utility import GodelUtilityEngine, SystemStateUtility, GodelProofDecision


class TestGodelUtility(unittest.TestCase):
    """Test suite for GodelUtilityEngine mathematical proof bounds."""

    def setUp(self):
        self.engine = GodelUtilityEngine()

    def test_authorizes_positive_utility_delta(self):
        s_curr = SystemStateUtility(0.80, 0.80, 1.0, 0.70)
        s_cand = SystemStateUtility(0.90, 0.85, 1.0, 0.75)
        dec = self.engine.evaluate_modification(s_curr, s_cand, "Safe Refactoring")
        self.assertIsInstance(dec, GodelProofDecision)
        self.assertTrue(dec.is_authorized)
        self.assertGreater(dec.delta_utility, 0.0)

    def test_prohibits_negative_utility_or_safety_degradation(self):
        s_curr = SystemStateUtility(0.90, 0.90, 1.0, 0.80)
        s_cand = SystemStateUtility(0.95, 0.95, 0.7, 0.90)  # Safety dropped
        dec = self.engine.evaluate_modification(s_curr, s_cand, "Unsafe Shortcut")
        self.assertFalse(dec.is_authorized)
        self.assertFalse(dec.safety_preserved)


if __name__ == "__main__":
    unittest.main()
