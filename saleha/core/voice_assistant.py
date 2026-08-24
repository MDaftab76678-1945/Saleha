"""
Saleha Core: Voice / Natural Speech Command Interface

Provides hands-free voice coding capabilities, capturing spoken developer instructions,
transcribing speech to text, and dispatching tasks to Saleha's autonomous orchestration pipeline.
"""

import sys
from dataclasses import dataclass
from typing import Optional, Dict, Any

from saleha.orchestrator import SalehaOrchestrator


@dataclass
class VoiceCommandResult:
    transcribed_text: str
    success: bool
    execution_result: Optional[str] = None
    error: Optional[str] = None


class VoiceAssistant:
    """Hands-free voice prompt listener and orchestrator dispatcher."""

    def __init__(self, model: str = "auto"):
        self.model = model
        self._orchestrator: Optional[SalehaOrchestrator] = None

    @property
    def orchestrator(self) -> SalehaOrchestrator:
        # Lazy init: import-time heavy construction (LLM clients, memory load)
        # se bachne ke liye orchestrator pehli actual use par banta hai.
        if self._orchestrator is None:
            self._orchestrator = SalehaOrchestrator(model=self.model)
        return self._orchestrator

    def process_voice_prompt(self, spoken_text: str, auto_execute: bool = True) -> VoiceCommandResult:
        """Processes transcribed natural language audio into an autonomous coding task."""
        clean_text = spoken_text.strip()
        if not clean_text:
            return VoiceCommandResult(
                transcribed_text="",
                success=False,
                error="No speech detected in audio input."
            )

        if not auto_execute:
            return VoiceCommandResult(
                transcribed_text=clean_text,
                success=True,
                execution_result="Prompt captured. Ready for execution."
            )

        try:
            res = self.orchestrator.execute_task(clean_text)
            return VoiceCommandResult(
                transcribed_text=clean_text,
                success=res.success,
                execution_result=res.final_code if res.success else res.log
            )
        except Exception as e:
            return VoiceCommandResult(
                transcribed_text=clean_text,
                success=False,
                error=f"Task execution failed: {str(e)}"
            )


# Global instance
voice_assistant = VoiceAssistant()

