"""Unit tests for the Autonomous Adversarial Red-Team Fuzzer (AgentShield)."""

import unittest
from saleha.core.red_team_engine import RedTeamEngine, RedTeamAuditReport


class TestRedTeamEngine(unittest.TestCase):
    """Test suite for RedTeamEngine adversarial fuzzing and exploit analysis."""

    def setUp(self):
        self.engine = RedTeamEngine(model="mock")

    def test_generate_adversarial_suite_creates_valid_tests(self):
        code = "def add(a, b): return a + b\n"
        suite = self.engine.generate_adversarial_suite(code)
        self.assertIsInstance(suite, str)
        self.assertIn("class ", suite)

    def test_audit_and_attack_hardened_code(self):
        hardened_code = (
            "def safe_divide(a, b):\n"
            "    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):\n"
            "        raise TypeError('Inputs must be numeric')\n"
            "    if b == 0:\n"
            "        raise ValueError('Division by zero')\n"
            "    return a / b\n"
        )
        report = self.engine.audit_and_attack(hardened_code, "safe_divide.py")
        self.assertIsInstance(report, RedTeamAuditReport)
        self.assertTrue(report.total_fuzz_tests_run >= 1)

    def test_standard_fuzz_vectors_present(self):
        self.assertTrue(len(self.engine.STANDARD_FUZZ_VECTORS) >= 5)
        self.assertTrue(any("DROP TABLE" in v for v in self.engine.STANDARD_FUZZ_VECTORS))


if __name__ == "__main__":
    unittest.main()
