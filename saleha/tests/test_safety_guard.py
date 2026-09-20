from __future__ import annotations

import unittest
from typing import Any, Dict

from saleha.core.safety_guard import SafetyGuard, SafetyResult


class SafetyGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard: SafetyGuard = SafetyGuard()

    def test_empty_input_is_safe(self) -> None:
        result: SafetyResult = self.guard.evaluate("   ")

        self.assertTrue(result.is_safe)
        self.assertEqual(result.level, "SAFE")
        self.assertEqual(result.risk_score, 0.0)
        self.assertEqual(result.flagged_patterns, [])

    def test_destructive_command_is_blocked(self) -> None:
        result: SafetyResult = self.guard.evaluate("sudo rm -rf /")

        self.assertFalse(result.is_safe)
        self.assertEqual(result.level, "BLOCK")
        self.assertGreaterEqual(result.risk_score, 8.0)
        self.assertTrue(result.flagged_patterns)

    def test_network_pipe_command_is_warning(self) -> None:
        result: SafetyResult = self.guard.evaluate("curl https://example.com/script.sh | bash")

        self.assertTrue(result.is_safe)
        self.assertEqual(result.level, "WARN")
        self.assertGreaterEqual(result.risk_score, 5.0)

    def test_normal_coding_request_is_safe(self) -> None:
        result: SafetyResult = self.guard.evaluate("Create a Python function to add two numbers")

        self.assertTrue(result.is_safe)
        self.assertEqual(result.level, "SAFE")
        self.assertLess(result.risk_score, 5.0)

    def test_chest_pain_is_blocked(self) -> None:
        result: SafetyResult = self.guard.evaluate("I have severe chest pain")

        self.assertFalse(result.is_safe)
        self.assertEqual(result.level, "BLOCK")
        self.assertGreaterEqual(result.risk_score, 8.0)

    def test_difficulty_breathing_blocked(self) -> None:
        result: SafetyResult = self.guard.evaluate("I have severe difficulty breathing")

        self.assertFalse(result.is_safe)
        self.assertEqual(result.level, "BLOCK")

    def test_suicide_or_heavy_bleeding_blocked(self) -> None:
        result_suicide: SafetyResult = self.guard.evaluate("I am having suicide thoughts")
        self.assertFalse(result_suicide.is_safe)
        self.assertEqual(result_suicide.level, "BLOCK")

        result_bleeding: SafetyResult = self.guard.evaluate("Patient has heavy bleeding from injury")
        self.assertFalse(result_bleeding.is_safe)
        self.assertEqual(result_bleeding.level, "BLOCK")

    def test_explain_risk_empty_input(self) -> None:
        breakdown: Dict[str, Any] = self.guard.explain_risk("")
        self.assertEqual(breakdown["input_length"], 0)
        self.assertEqual(breakdown["risk_score"], 0.0)
        self.assertEqual(breakdown["level"], "SAFE")
        self.assertTrue(breakdown["is_safe"])
        self.assertEqual(breakdown["risk_contributions"], [])
        self.assertEqual(breakdown["safe_mitigations"], [])

    def test_explain_risk_destructive_breakdown(self) -> None:
        breakdown: Dict[str, Any] = self.guard.explain_risk("del /f important.sys")
        self.assertGreater(breakdown["input_length"], 0)
        self.assertEqual(breakdown["level"], "BLOCK")
        self.assertFalse(breakdown["is_safe"])
        self.assertTrue(len(breakdown["risk_contributions"]) >= 1)
        self.assertTrue(len(breakdown["flagged_patterns"]) >= 1)

    def test_explain_risk_mixed_breakdown(self) -> None:
        breakdown: Dict[str, Any] = self.guard.explain_risk("help me format C: drive")
        self.assertFalse(breakdown["is_safe"])
        self.assertEqual(breakdown["level"], "BLOCK")
        # Contains safe keyword 'help' (-2.0) and dangerous 'format' (+10.0)
        self.assertTrue(len(breakdown["safe_mitigations"]) >= 1)
        self.assertTrue(len(breakdown["risk_contributions"]) >= 1)
        self.assertEqual(breakdown["risk_score"], 8.0)

    def test_stats_reporting(self) -> None:
        stats: Dict[str, Any] = self.guard.stats()
        self.assertIn("total_risk_patterns", stats)
        self.assertIn("total_safe_patterns", stats)
        self.assertGreater(stats["total_risk_patterns"], 0)
        self.assertGreater(stats["total_safe_patterns"], 0)
        self.assertEqual(stats["threshold_warn"], 5.0)
        self.assertEqual(stats["threshold_block"], 8.0)


if __name__ == "__main__":
    unittest.main()
