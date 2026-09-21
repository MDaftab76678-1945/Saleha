"""
Saleha Core: Speech Backends (Real Voice -- STT + TTS)

Provides optional speech-to-text and text-to-speech backends:
  STT: faster-whisper  (local Whisper, CPU int8, offline)
  TTS: pyttsx3         (Windows SAPI / espeak, offline)

Graceful degradation on both sides: if the package is missing, `available()`
returns False and callers receive clean error diagnostics.
Model instances are lazy-loaded and cached for low-latency calls.

Install: pip install saleha[voice]
"""

from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

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
                 device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    @staticmethod
    def available() -> bool:
        try:
            importlib.import_module("faster_whisper")
            return True
        except (ImportError, Exception):
            return False

    def _get_model(self) -> Any:
        if self._model is None:
            fw = importlib.import_module("faster_whisper")
            whisper_model_cls = fw.WhisperModel
            self._model = whisper_model_cls(
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

    def __init__(self, rate: int = 170, volume: float = 1.0) -> None:
        self.rate = rate
        self.volume = volume

    @staticmethod
    def available() -> bool:
        try:
            importlib.import_module("pyttsx3")
            return True
        except (ImportError, Exception):
            return False

    def speak(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        try:
            pyttsx3_mod = importlib.import_module("pyttsx3")
            engine = pyttsx3_mod.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", max(0.0, min(1.0, self.volume)))
            # Truncate long output -- speak the first line/summary up to 300 characters.
            spoken = text.strip().splitlines()[0][:300]
            engine.say(spoken)
            engine.runAndWait()
            return True
        except Exception:
            return False


# ==============================================================================
# High-level convenience
# ==============================================================================

def get_status() -> Dict[str, bool]:
    """Availability snapshot for system health diagnostics."""
    return {
        "stt_whisper": WhisperSTT.available(),
        "tts_pyttsx3": PyttsxTTS.available(),
    }
