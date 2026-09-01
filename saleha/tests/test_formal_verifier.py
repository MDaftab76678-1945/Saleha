"""Unit tests for Formal Verification Invariant Prover."""

import unittest
from saleha.core.formal_verifier import FormalVerifier, FormalProofReport


class TestFormalVerifier(unittest.TestCase):
    """Test suite for FormalVerifier logic proofs and bounds checking."""

    def setUp(self):
        self.verifier = FormalVerifier()

    def test_verify_guarded_division(self):
        code = (
            "def divide(a, b):\n"
            "    assert b != 0\n"
            "    return a / b\n"
        )
        rep = self.verifier.verify_code(code, "divide.py")
        self.assertIsInstance(rep, FormalProofReport)
        self.assertTrue(rep.is_formally_sound)
        self.assertTrue(any(p.invariant_type == "precondition" for p in rep.proofs))

    def test_detects_division_by_zero_violation(self):
        code = (
            "def broken():\n"
            "    return 10 / 0\n"
        )
        rep = self.verifier.verify_code(code, "broken.py")
        self.assertFalse(rep.is_formally_sound)
        self.assertTrue(any(not p.proved for p in rep.proofs))


if __name__ == "__main__":
    unittest.main()
