"""Unit tests for 4D Cognitive State Engine."""

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
        self.assertEqual(report.ethical.rating, "EXCELLENT")

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
