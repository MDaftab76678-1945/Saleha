"""Unit tests for Full-Duplex Voice Assistant Engine."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from saleha.core.voice_engine import VoiceAssistantEngine, VoiceInteractionResult
from saleha.agents.base_agent import AgentResponse


class VoiceEngineTests(unittest.TestCase):

    def setUp(self):
        self.engine = VoiceAssistantEngine()

    def test_process_voice_command_success(self):
        with patch.object(self.engine.agent, "think") as mock_think:
            mock_think.return_value = AgentResponse(
                success=True,
                content="Understood. Running unit tests and fixing the auth token error now."
            )
            res = self.engine.process_voice_command("Fix the auth token error", simulate_audio=True)
            self.assertTrue(res.success)
            self.assertEqual(res.recognized_transcript, "Fix the auth token error")
            self.assertIn("Running unit tests", res.response_text)
            self.assertIsNotNone(res.audio_output_path)

    def test_process_empty_voice_command(self):
        res = self.engine.process_voice_command("", simulate_audio=False)
        self.assertFalse(res.success)
        self.assertIn("did not hear", res.response_text)


if __name__ == "__main__":
    unittest.main()

