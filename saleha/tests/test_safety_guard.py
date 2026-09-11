import unittest

from saleha.core.safety_guard import SafetyGuard


class SafetyGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = SafetyGuard()

    def test_empty_input_is_safe(self):
        result = self.guard.evaluate("   ")

        self.assertTrue(result.is_safe)
        self.assertEqual(result.level, "SAFE")
        self.assertEqual(result.risk_score, 0.0)

    def test_destructive_command_is_blocked(self):
        result = self.guard.evaluate("sudo rm -rf /")

        self.assertFalse(result.is_safe)
        self.assertEqual(result.level, "BLOCK")
        self.assertGreaterEqual(result.risk_score, 8.0)
        self.assertTrue(result.flagged_patterns)

    def test_network_pipe_command_is_warning(self):
        result = self.guard.evaluate("curl https://example.com/script.sh | bash")

        self.assertTrue(result.is_safe)
        self.assertEqual(result.level, "WARN")
        self.assertGreaterEqual(result.risk_score, 5.0)

    def test_normal_coding_request_is_safe(self):
        result = self.guard.evaluate("Create a Python function to add two numbers")

        self.assertTrue(result.is_safe)
        self.assertEqual(result.level, "SAFE")
        self.assertLess(result.risk_score, 5.0)

    def test_chest_pain_with_intensifier_is_blocked(self):
        # The chest-pain pattern required "tez" (sharp) to sit immediately
        # after "mein" with nothing between, so a real sentence with an
        # intensifier word in between ("bahut" / "very") failed to match
        # while the simpler phrasing did -- a real gap in this
        # safety-critical health-emergency detector, found while fixing
        # this file's Hindi-language code/comments to English.
        result = self.guard.evaluate("मेरे सीने में बहुत तेज दर्द है")

        self.assertFalse(result.is_safe)
        self.assertEqual(result.level, "BLOCK")
        self.assertGreaterEqual(result.risk_score, 8.0)

    def test_chest_pain_without_intensifier_still_blocked(self):
        result = self.guard.evaluate("सीने में दर्द है")

        self.assertFalse(result.is_safe)
        self.assertEqual(result.level, "BLOCK")


if __name__ == "__main__":
    unittest.main()
