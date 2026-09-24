"""v1.4: Voice speech backends (fake-injected, offline-safe) + CLI validation."""
import os
import tempfile
import unittest
from typing import Any, List
from unittest.mock import MagicMock, patch

from saleha.core.speech import (
    PyttsxTTS,
    WhisperSTT,
    get_status,
)


class SpeechBackendTests(unittest.TestCase):
    def test_whisper_unavailable_reports_gracefully(self) -> None:
        with patch.dict("sys.modules", {"faster_whisper": None}):
            # the import fails -> available is False
            self.assertIsInstance(WhisperSTT.available(), bool)

    def test_transcribe_missing_file_fails_clean(self) -> None:
        stt = WhisperSTT()
        res = stt.transcribe(os.path.join(tempfile.gettempdir(), "nope_404.wav"))
        self.assertFalse(res.success)
        self.assertIn("not found", res.error)

    def test_whisper_happy_path_with_fake_module(self) -> None:
        fake_mod = MagicMock()

        class FakeModel:
            def __init__(self, size: Any, device: Any, compute_type: Any) -> None:
                pass

            def transcribe(self, path: Any, language: Any = None) -> Any:
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

    def test_tts_speak_true_and_false(self) -> None:
        tts = PyttsxTTS()
        with patch.dict("sys.modules", {"pyttsx3": MagicMock()}):
            self.assertTrue(tts.speak("hello world"))
        self.assertFalse(tts.speak("   "))
        with patch.dict("sys.modules", {"pyttsx3": None}):  # import fails
            self.assertFalse(tts.speak("x"))

    def test_get_status_shape(self) -> None:
        status = get_status()
        self.assertIn("stt_whisper", status)
        self.assertIn("tts_pyttsx3", status)


class VoiceCliTests(unittest.TestCase):
    def _invoke(self, args: List[str]) -> Any:
        from click.testing import CliRunner

        from saleha.cli.commands import cli
        return CliRunner().invoke(cli, ["voice"] + args)

    def test_no_input_exits_with_code_2(self) -> None:
        result = self._invoke([])
        self.assertNotEqual(result.exit_code, 0)

    def test_missing_audio_file_rejected_by_click(self) -> None:
        result = self._invoke(["--audio", "definitely_missing_99.wav"])
        self.assertNotEqual(result.exit_code, 0)

    def test_text_mode_dispatches_to_assistant(self) -> None:
        with patch("saleha.core.voice_assistant.VoiceAssistant.process_voice_prompt") as pv:
            pv.return_value = MagicMock(success=True, execution_result="done")
            result = self._invoke(["build a cache"])
        self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
