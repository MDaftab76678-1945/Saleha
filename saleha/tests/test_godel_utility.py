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


# ---------------------------------------------------------------------------
# Regression: `saleha godel-utility` built both states from literals --
#   s_curr = SystemStateUtility(0.92, 0.88, 1.0, 0.75)
#   s_cand = SystemStateUtility(0.96, 0.94, 1.0, 0.82)
# -- and printed "AUTHORIZED (SafetyOK=True)" about a refactoring that did not
# exist. The engine's maths was sound; the inputs were invented.
# ---------------------------------------------------------------------------

from saleha.core.godel_utility import measure_current_state


class MeasuredStateTests(unittest.TestCase):

    def test_direct_construction_stays_trusted(self):
        """The long-standing API: caller supplies numbers and vouches for them."""
        s = SystemStateUtility(0.8, 0.8, 1.0, 0.7)
        self.assertEqual(s.unmeasured_fields, [])
        self.assertTrue(s.fully_measured)

    def test_unmeasured_field_is_reported(self):
        s = SystemStateUtility(0.0, 0.9, 0.9, 0.9,
                               measured={"alignment_score": False,
                                         "task_pass_rate": True,
                                         "safety_score": True,
                                         "efficiency_score": True})
        self.assertEqual(s.unmeasured_fields, ["alignment_score"])
        self.assertFalse(s.fully_measured)

    def test_proof_over_unmeasured_inputs_is_inconclusive_not_authorized(self):
        """A utility proof over invented numbers proves nothing."""
        engine = GodelUtilityEngine()
        flags = {"alignment_score": False, "task_pass_rate": True,
                 "safety_score": True, "efficiency_score": True}
        low = SystemStateUtility(0.0, 0.5, 0.9, 0.5, measured=flags)
        high = SystemStateUtility(0.0, 0.9, 0.9, 0.9, measured=flags)
        dec = engine.evaluate_modification(low, high, "refactor")
        self.assertGreater(dec.delta_utility, 0.0)   # maths still holds
        self.assertFalse(dec.is_authorized)          # but proves nothing
        self.assertIn("INCONCLUSIVE", dec.proof_summary)
        self.assertIn("alignment_score", dec.proof_summary)
        self.assertNotIn("AUTHORIZED", dec.proof_summary)

    def test_fully_measured_states_can_still_authorize(self):
        engine = GodelUtilityEngine()
        flags = {k: True for k in ("alignment_score", "task_pass_rate",
                                   "safety_score", "efficiency_score")}
        low = SystemStateUtility(0.8, 0.5, 0.9, 0.5, measured=flags)
        high = SystemStateUtility(0.8, 0.9, 0.9, 0.9, measured=flags)
        dec = engine.evaluate_modification(low, high, "refactor")
        self.assertTrue(dec.is_authorized)
        self.assertIn("AUTHORIZED", dec.proof_summary)

    def test_measure_current_state_records_provenance(self):
        s = measure_current_state()
        for key in ("alignment_score", "task_pass_rate",
                    "safety_score", "efficiency_score"):
            self.assertIn(key, s.measured)

    def test_alignment_is_never_self_scored(self):
        """A system rating its own alignment is the trust failure this repo
        keeps finding; it must stay unmeasured rather than be invented."""
        s = measure_current_state()
        self.assertEqual(s.alignment_score, 0.0)
        self.assertFalse(s.measured["alignment_score"])
        self.assertIn("alignment_score", s.unmeasured_fields)

    def test_measured_values_are_in_range(self):
        s = measure_current_state()
        for value in (s.task_pass_rate, s.safety_score,
                      s.efficiency_score, s.alignment_score):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_safety_is_measured_from_real_source(self):
        """saleha/core exists, so the constitutional scan must produce a value."""
        s = measure_current_state()
        self.assertTrue(s.measured["safety_score"])
