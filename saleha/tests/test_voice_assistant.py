"""Unit tests for Jarvis Voice Assistant Engine."""

import unittest
from saleha.core.voice_assistant import VoiceAssistant, VoiceCommandResult


class TestVoiceAssistant(unittest.TestCase):
    """Test suite for VoiceAssistant intent extraction and command execution."""

    def setUp(self):
        self.va = VoiceAssistant(wake_word="jarvis", tts_enabled=False)

    def test_is_wake_word_detection(self):
        self.assertTrue(self.va.is_wake_word("Jarvis, build a web server"))
        self.assertTrue(self.va.is_wake_word("hey saleha, what is the time?"))
        self.assertFalse(self.va.is_wake_word("hello world"))

    def test_extract_intent(self):
        intent = self.va.extract_intent("Jarvis, create a FastAPI app")
        self.assertEqual(intent, "create a FastAPI app")

    def test_process_exit_words(self):
        res = self.va.process_voice_input("goodbye")
        self.assertTrue(res.success)
        self.assertEqual(res.action_executed, "exit")

    def test_process_with_custom_executor(self):
        def mock_executor(goal: str) -> str:
            return f"Processed: {goal}"

        res = self.va.process_voice_input("Jarvis, write code", executor_fn=mock_executor)
        self.assertTrue(res.success)
        self.assertEqual(res.response_text, "Processed: write code")


if __name__ == "__main__":
    unittest.main()
