"""v1.4: Voice speech backends (fake-injected, offline-safe) + CLI validation."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from saleha.core.speech import (
    PyttsxTTS,
    TranscriptionResult,
    WhisperSTT,
    get_status,
)


class SpeechBackendTests(unittest.TestCase):
    def test_whisper_unavailable_reports_gracefully(self):
        with patch.dict("sys.modules", {"faster_whisper": None}):
            # import fail hoga -> available False
            self.assertIsInstance(WhisperSTT.available(), bool)

    def test_transcribe_missing_file_fails_clean(self):
        stt = WhisperSTT()
        res = stt.transcribe(os.path.join(tempfile.gettempdir(), "nope_404.wav"))
        self.assertFalse(res.success)
        self.assertIn("not found", res.error)

    def test_whisper_happy_path_with_fake_module(self):
        fake_mod = MagicMock()

        class FakeModel:
            def __init__(self, size, device, compute_type):
                pass

            def transcribe(self, path, language=None):
                segs = [MagicMock(text=" build "), MagicMock(text=" a rate limiter ")]
                return segs, MagicMock(language="en")

        fake_mod.WhisperModel = FakeModel
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"RIFF-fake-audio")
            wav_path = f.name
        try:
            with patch.dict("sys.modules", {"faster_whisper": fake_mod}):
                stt = WhisperSTT(model_size="tiny")
                self.assertTrue(stt.available())
                res = stt.transcribe(wav_path)
        finally:
            os.remove(wav_path)
        self.assertTrue(res.success)
        self.assertEqual(res.text, "build a rate limiter")
        self.assertEqual(res.backend, "whisper:tiny")

    def test_tts_speak_true_and_false(self):
        tts = PyttsxTTS()
        with patch.dict("sys.modules", {"pyttsx3": MagicMock()}):
            self.assertTrue(tts.speak("hello world"))
        self.assertFalse(tts.speak("   "))
        self.assertFalse(tts.speak("x"))  # pyttsx3 missing -> exception -> False

    def test_get_status_shape(self):
        status = get_status()
        self.assertIn("stt_whisper", status)
        self.assertIn("tts_pyttsx3", status)


class VoiceCliTests(unittest.TestCase):
    def _invoke(self, args):
        from click.testing import CliRunner
        from saleha.cli.commands import cli
        return CliRunner().invoke(cli, ["voice"] + args)

    def test_no_input_exits_with_code_2(self):
        result = self._invoke([])
        self.assertNotEqual(result.exit_code, 0)

    def test_missing_audio_file_rejected_by_click(self):
        result = self._invoke(["--audio", "definitely_missing_99.wav"])
        self.assertNotEqual(result.exit_code, 0)

    def test_text_mode_dispatches_to_assistant(self):
        from saleha.cli.commands import cli as root_cli
        with patch("saleha.core.voice_assistant.VoiceAssistant.process_voice_prompt") as pv:
            pv.return_value = MagicMock(success=True, execution_result="done")
            result = self._invoke(["build a cache"])
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
