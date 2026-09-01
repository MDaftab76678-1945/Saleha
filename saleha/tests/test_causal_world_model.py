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


if __name__ == "__main__":
    unittest.main()
