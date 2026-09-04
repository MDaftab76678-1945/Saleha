#==============================================================================
# J.A.R.V.I.S. WHISPER STT ENGINE (TensorRT/faster-whisper Integration)
#==============================================================================

import numpy as np
import time
from typing import Optional, Generator

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


class JarvisWhisperSTT:
    """
    Local Offline Speech-to-Text Engine using faster-whisper.
    Supports INT8 CPU quantization for low-latency transcription.
    """

    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        self.model = None
        self.model_size = model_size

        if HAS_WHISPER:
            try:
                print(f"⚡ [LOADING LOCAL FASTER-WHISPER ({model_size})...]")
                self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
                print("✅ [FASTER-WHISPER ONLINE]: Local STT Engine Ready.")
            except Exception as e:
                print(f"⚠ Faster-Whisper init failed: {e}")
        else:
            print("⚠ faster-whisper not installed. STT disabled.")

    def transcribe_pcm(self, pcm_data: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribes raw PCM audio data to text.
        """
        if not self.model:
            return ""

        try:
            start_time = time.perf_counter()

            # Convert PCM to float32 if needed
            if pcm_data.dtype == np.int16:
                audio_float = pcm_data.astype(np.float32) / 32768.0
            else:
                audio_float = pcm_data

            # Transcribe
            segments, info = self.model.transcribe(
                audio_float,
                beam_size=3,
                language="en",
                vad_filter=True
            )

            # Collect all segments
            text = "".join([segment.text for segment in segments]).strip()

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            print(f"⚡ [WHISPER STT] Transcribed {len(audio_float)/sample_rate:.2f}s audio in {elapsed_ms:.1f}ms")

            return text

        except Exception as e:
            print(f"❌ [WHISPER STT ERROR]: {e}")
            return ""

    def transcribe_streaming(self, pcm_chunks: Generator[np.ndarray, None, None]) -> Generator[str, None, None]:
        """
        Streaming transcription for real-time audio chunks.
        """
        if not self.model:
            return

        buffer = []

        for chunk in pcm_chunks:
            buffer.append(chunk)

            # Process every 2 seconds of audio
            if len(buffer) * len(chunk) >= 32000:  # 2 seconds @ 16kHz
                audio = np.concatenate(buffer)
                text = self.transcribe_pcm(audio)

                if text:
                    yield text

                buffer = []


if __name__ == "__main__":
    # Test STT Engine
    stt = JarvisWhisperSTT(model_size="base.en")

    # Generate test audio (sine wave)
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    test_audio = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)

    result = stt.transcribe_pcm(test_audio, sample_rate)
    print(f"Transcription result: {result}")
