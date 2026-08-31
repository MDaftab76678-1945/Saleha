"""Unit tests for Full-Duplex Real-Time Voice Terminal Assistant."""

from __future__ import annotations

import unittest
from saleha.core.voice_live import VoiceLiveAssistant, VoiceCommand
from saleha.core.speech import PyttsxTTS, WhisperSTT


class VoiceLiveAssistantTests(unittest.TestCase):

    def setUp(self):
        self.assistant = VoiceLiveAssistant()

    def test_classify_intent_fix(self):
        cmd = self.assistant.classify_intent("Please fix auth.py syntax error")
        self.assertEqual(cmd.intent, "FIX")
        self.assertIn("auth.py", cmd.target_arg)

    def test_classify_intent_test(self):
        cmd = self.assistant.classify_intent("Run pytest suite")
        self.assertEqual(cmd.intent, "TEST")

    def test_classify_intent_review(self):
        cmd = self.assistant.classify_intent("Review security vulnerabilities in saleha/core")
        self.assertEqual(cmd.intent, "REVIEW")

    def test_classify_intent_diff_and_status(self):
        diff_cmd = self.assistant.classify_intent("Show blast radius and diff changes")
        self.assertEqual(diff_cmd.intent, "DIFF")

        status_cmd = self.assistant.classify_intent("Saleha status check")
        self.assertEqual(status_cmd.intent, "STATUS")

        exit_cmd = self.assistant.classify_intent("Stop listening and quit")
        self.assertEqual(exit_cmd.intent, "EXIT")

    def test_process_turn_executes_and_responds(self):
        turn = self.assistant.process_turn("Fix unit tests in test_vault.py", speak=False)
        self.assertTrue(turn.success)
        self.assertEqual(turn.command.intent, "FIX")
        self.assertIn("Auto-healing", turn.action_summary)
        self.assertGreater(turn.duration_sec, 0.0)


if __name__ == "__main__":
    unittest.main()

