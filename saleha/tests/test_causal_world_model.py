"""Unit tests for Pearl's Structural Causal World Model."""

import unittest
from saleha.core.causal_world_model import CausalWorldModel, CausalEvaluationReport


class TestCausalWorldModel(unittest.TestCase):
    """Test suite for CausalWorldModel L1, L2, and L3 reasoning."""

    def setUp(self):
        self.cwm = CausalWorldModel()

    def test_l1_association_query(self):
        val = self.cwm.query_l1_association({"use_async_io": True}, "latency_ms")
        self.assertIsInstance(val, float)
        self.assertLess(val, 150.0)

    def test_l2_intervention_simulation(self):
        rep = self.cwm.simulate_l2_intervention({"high_test_coverage": True}, "defect_rate")
        self.assertIsInstance(rep, CausalEvaluationReport)
        self.assertEqual(rep.inquiry_level, "L2_Intervention")
        self.assertLess(rep.expected_outcome, 0.02)

    def test_l3_counterfactual_evaluation(self):
        rep = self.cwm.evaluate_l3_counterfactual(
            factual_state={"use_async_io": False},
            counterfactual_action={"use_async_io": True},
            target="throughput_rps",
        )
        self.assertEqual(rep.inquiry_level, "L3_Counterfactual")
        self.assertGreater(rep.expected_outcome, 200.0)

    def test_intervention_severs_incoming_edges(self):
        """
        do(X=x) means X is set by the intervention, not produced by its causes,
        so its incoming edges are cut. That step did not exist:
        simulate_l2_intervention called the association query directly, so
        "doing" and "observing" returned the same number under two names.
        """
        rep = self.cwm.simulate_l2_intervention(
            {"latency_ms": True, "use_async_io": True}, "latency_ms")
        self.assertIn("use_async_io -> latency_ms", rep.severed_edges)
        self.assertIn("has_memory_cache -> latency_ms", rep.severed_edges)
        self.assertTrue(rep.differs_from_association)
        self.assertNotEqual(rep.expected_outcome, rep.association_outcome)

    def test_no_severable_edges_is_reported_not_hidden(self):
        """
        Intervening on a root variable severs nothing, so the answer legitimately
        matches association. Saying so is different from never having looked.
        """
        rep = self.cwm.simulate_l2_intervention({"use_async_io": True}, "latency_ms")
        self.assertEqual(rep.severed_edges, [])
        self.assertFalse(rep.differs_from_association)
        self.assertIn("No edges severed", rep.reasoning)

    def test_l3_does_not_claim_abduction_it_never_performs(self):
        """Pearl's L3 is abduction -> action -> prediction; there is no noise
        model here, so abduction cannot run."""
        rep = self.cwm.evaluate_l3_counterfactual(
            factual_state={"use_async_io": False},
            counterfactual_action={"use_async_io": True},
            target="latency_ms",
        )
        self.assertFalse(rep.abduction_performed)
        self.assertIn("no abduction step", rep.reasoning)


if __name__ == "__main__":
    unittest.main()
