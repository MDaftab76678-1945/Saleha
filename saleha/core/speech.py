"""
Saleha Core: Speech Backends (Real Voice -- STT + TTS)

Pehle `saleha voice` sirf typed text ko pipeline me daal deta tha --
asli audio kabhi suna hi nahi jaata tha. Ab (sab OPTIONAL deps ke saath):

  STT: faster-whisper  (local Whisper, CPU int8, koi cloud nahi)
  TTS: pyttsx3         (Windows SAPI / espeak, offline)

Graceful degradation dono taraf: package na ho to `available()` False
aur caller ko clear message milta hai. Model instance lazy-load +
cache hota hai (pehli call slow, baaki instant).

Install: pip install saleha[voice]
"""

import os
import time
from dataclasses import dataclass, field
from typing import Optional


# ==============================================================================
# STT -- faster-whisper
# ==============================================================================

@dataclass
class TranscriptionResult:
    success: bool
    text: str = ""
    language: str = ""
    duration_sec: float = 0.0
    backend: str = ""
    error: str = ""


class WhisperSTT:
    """Local speech-to-text via faster-whisper. Model lazy-load + cached."""

    def __init__(self, model_size: str = "base",
                 device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    @staticmethod
    def available() -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size, device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(self, audio_path: str,
                   language: Optional[str] = None) -> TranscriptionResult:
        start = time.time()
        if not os.path.isfile(audio_path):
            return TranscriptionResult(False, backend="whisper",
                                       error=f"audio file not found: {audio_path}")
        try:
            model = self._get_model()
            segments, info = model.transcribe(audio_path, language=language)
            text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
            return TranscriptionResult(
                success=True,
                text=text.strip(),
                language=getattr(info, "language", "") or "",
                duration_sec=round(time.time() - start, 2),
                backend=f"whisper:{self.model_size}",
            )
        except Exception as exc:
            return TranscriptionResult(False, backend="whisper",
                                       error=f"transcription failed: {exc}")


# ==============================================================================
# TTS -- pyttsx3
# ==============================================================================

class PyttsxTTS:
    """Offline text-to-speech (Windows SAPI / espeak / nsss)."""

    def __init__(self, rate: int = 170, volume: float = 1.0):
        self.rate = rate
        self.volume = volume

    @staticmethod
    def available() -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except ImportError:
            return False

    def speak(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", max(0.0, min(1.0, self.volume)))
            # Lambi output truncate -- poora code padhna boring hai
            spoken = text.strip().splitlines()[0][:300]
            engine.say(spoken)
            engine.runAndWait()
            return True
        except Exception:
            return False


# ==============================================================================
# High-level convenience
# ==============================================================================

def get_status() -> dict:
    """Doctor/metrics ke liye availability snapshot."""
    return {
        "stt_whisper": WhisperSTT.available(),
        "tts_pyttsx3": PyttsxTTS.available(),
    }
