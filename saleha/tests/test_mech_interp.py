"""Unit tests for Mechanistic Interpretability & Circuit Attribution."""

import unittest
from saleha.core.mech_interp import MechInterpEngine, MechInterpReport


class TestMechInterp(unittest.TestCase):
    """Test suite for MechInterpEngine circuit discovery and attribution."""

    def setUp(self):
        self.engine = MechInterpEngine()

    def test_explain_code_discovers_circuits(self):
        sample_code = (
            "def safe_divide(a: int, b: int) -> float:\n"
            "    if b == 0:\n"
            "        raise ValueError('Divisor cannot be zero')\n"
            "    return float(a / b)\n"
        )
        rep = self.engine.explain_code(sample_code, "math_utils.py")
        self.assertIsInstance(rep, MechInterpReport)
        self.assertEqual(rep.target_name, "math_utils.py")
        self.assertGreater(rep.circuits_identified["error_guard"], 0)
        self.assertGreater(rep.circuits_identified["type_contract"], 0)
        self.assertEqual(len(rep.attributions), 4)


if __name__ == "__main__":
    unittest.main()
