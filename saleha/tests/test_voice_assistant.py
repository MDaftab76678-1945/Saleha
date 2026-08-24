"""Unit tests for Voice / Natural Speech Command Interface."""

import unittest
from saleha.core.voice_assistant import VoiceAssistant


class VoiceAssistantTests(unittest.TestCase):

    def setUp(self):
        self.assistant = VoiceAssistant(model="auto")

    def test_empty_speech_fails(self):
        res = self.assistant.process_voice_prompt("   ", auto_execute=False)
        self.assertFalse(res.success)
        self.assertIn("No speech detected", res.error)

    def test_voice_prompt_capture_without_execution(self):
        res = self.assistant.process_voice_prompt("Create a token bucket rate limiter", auto_execute=False)
        self.assertTrue(res.success)
        self.assertEqual(res.transcribed_text, "Create a token bucket rate limiter")


if __name__ == "__main__":
    unittest.main()

