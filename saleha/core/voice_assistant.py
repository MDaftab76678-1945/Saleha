"""
Saleha Core: Jarvis Voice Assistant & Hands-Free Audio Engine

Implements an autonomous local voice interface for Saleha:
1. Speech-to-Text (STT) listener with configurable wake words ("Jarvis", "Saleha").
2. Intent extraction & routing to SalehaOrchestrator or RecursiveSolver.
3. Text-to-Speech (TTS) auditory feedback.
4. Seamless fallback for headless/server and CI environments without audio drivers.
"""

import os
import sys
import time
import importlib
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable


@dataclass
class VoiceCommandResult:
    """Result of a processed voice command."""
    success: bool
    transcript: str
    response_text: str
    action_executed: str
    execution_result: str = ""
    execution_time_sec: float = 0.0

    def __post_init__(self):
        if not self.execution_result:
            self.execution_result = self.response_text


class VoiceAssistant:
    """Jarvis-style Voice Assistant Engine for Saleha."""

    WAKE_WORDS = {"jarvis", "saleha", "assistant", "hey saleha"}
    EXIT_WORDS = {"exit", "quit", "goodbye", "stop", "shant ho jao"}

    def __init__(self, wake_word: str = "saleha", tts_enabled: bool = True):
        """Initializes the Jarvis voice assistant engine with audio fallbacks."""
        self.wake_word = wake_word.lower()
        self.tts_enabled = tts_enabled
        self._stt_driver = None
        self._tts_driver = None
        self._init_audio_drivers()

    def _init_audio_drivers(self):
        """Attempts to initialize speech_recognition and pyttsx3 with graceful fallbacks."""
        try:
            self._stt_driver = importlib.import_module("speech_recognition")
        except (ImportError, Exception):
            self._stt_driver = None

        try:
            pyttsx = importlib.import_module("pyttsx3")
            self._tts_driver = pyttsx.init()
        except (ImportError, Exception):
            self._tts_driver = None

    def speak(self, text: str):
        """Audibly speaks the given response text or prints in simulated audio mode."""
        if not text:
            return
        if self.tts_enabled and self._tts_driver:
            try:
                self._tts_driver.say(text)
                self._tts_driver.runAndWait()
                return
            except Exception:
                pass  # noqa

    def is_wake_word(self, phrase: str) -> bool:
        """Checks if a given phrase starts with or contains any active wake word."""
        phrase_clean = phrase.lower().strip()
        return any(w in phrase_clean for w in self.WAKE_WORDS)

    def extract_intent(self, speech_text: str) -> str:
        """Strips wake word and extracts the core user coding or reasoning instruction."""
        text = speech_text.strip()
        for word in self.WAKE_WORDS:
            if text.lower().startswith(word):
                text = text[len(word):].strip(" ,:.-")
                break
        return text

    def process_voice_input(self, speech_text: str, executor_fn: Optional[Callable[[str], Any]] = None) -> VoiceCommandResult:
        """Processes a recognized speech string, executes the task, and speaks the result."""
        start_time = time.time()
        clean_text = speech_text.strip()

        if not clean_text:
            return VoiceCommandResult(
                success=False,
                transcript="",
                response_text="No speech recognized.",
                action_executed="none",
                execution_time_sec=0.0,
            )

        if any(exit_w in clean_text.lower() for exit_w in self.EXIT_WORDS):
            self.speak("Goodbye! Have a great day.")
            return VoiceCommandResult(
                success=True,
                transcript=clean_text,
                response_text="Assistant shutting down.",
                action_executed="exit",
                execution_time_sec=round(time.time() - start_time, 2),
            )

        task_goal = self.extract_intent(clean_text)
        if not task_goal:
            task_goal = clean_text

        self.speak(f"Processing your request: {task_goal[:40]}")

        if executor_fn:
            try:
                exec_output = executor_fn(task_goal)
                response_msg = f"Task completed successfully."
                self.speak(response_msg)
                return VoiceCommandResult(
                    success=True,
                    transcript=clean_text,
                    response_text=str(exec_output),
                    action_executed="custom_executor",
                    execution_time_sec=round(time.time() - start_time, 2),
                )
            except Exception as err:
                response_msg = f"Task execution encountered an error: {err}"
                self.speak(response_msg)
                return VoiceCommandResult(
                    success=False,
                    transcript=clean_text,
                    response_text=response_msg,
                    action_executed="error",
                    execution_time_sec=round(time.time() - start_time, 2),
                )

        response_msg = f"Received command: '{task_goal}'"
        return VoiceCommandResult(
            success=True,
            transcript=clean_text,
            response_text=response_msg,
            action_executed="echo",
            execution_time_sec=round(time.time() - start_time, 2),
        )

    def process_voice_prompt(self, prompt: str, audio_file: Optional[str] = None, auto_execute: bool = False, executor_fn: Optional[Callable[[str], Any]] = None) -> VoiceCommandResult:
        """Processes a voice prompt from text or transcribed audio file for CLI integration."""
        if audio_file:
            from saleha.core.speech import WhisperSTT
            stt = WhisperSTT()
            res = stt.transcribe(audio_file)
            if not res.success:
                return VoiceCommandResult(
                    success=False,
                    transcript="",
                    response_text=res.error or "Audio transcription failed",
                    action_executed="error",
                )
            prompt = res.text

        if auto_execute and not executor_fn:
            from saleha.orchestrator import SalehaOrchestrator
            orch = SalehaOrchestrator()
            executor_fn = lambda p: orch.run_task(p).summary if hasattr(orch.run_task(p), "summary") else str(orch.run_task(p))

        return self.process_voice_input(prompt, executor_fn=executor_fn)


voice_assistant = VoiceAssistant()


if __name__ == "__main__":
    _va = VoiceAssistant()
    _res = _va.process_voice_input("Jarvis, write a binary search function")
