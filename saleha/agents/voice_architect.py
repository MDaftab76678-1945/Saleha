"""VoiceArchitectAgent: 25th Autonomous Agent for Real-Time Spoken Pair-Programming & Audio Commentary."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from saleha.agents.base_agent import AgentResponse, BaseAgent


@dataclass
class VoiceCommentaryResult:
    """Represents spoken voice commentary for a development task."""
    topic: str
    transcript: str
    audio_duration_estimate_sec: float
    cadence: str  # energetic, conversational, technical
    bullet_talking_points: List[str]
    generation_time_ms: float


class VoiceArchitectAgent(BaseAgent):
    """25th Autonomous Python Agent for real-time voice pair-programming and verbal architecture walkthroughs."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Voice Architect & Spoken Pair Programmer", model=model)
        self.name = "VoiceArchitectAgent"

    def execute(self, prompt: str, **kwargs) -> AgentResponse:
        """Executes the voice commentary synthesis."""
        start = time.perf_counter()
        result = self.synthesize_voice_commentary(prompt)
        duration = time.perf_counter() - start

        content = (
            f"[VoiceArchitectAgent] Draft speaking notes for: \"{result.topic}\" "
            f"(no audio was synthesized)\n\n"
            f"Verbal Audio Transcript ({result.audio_duration_estimate_sec}s spoken estimate):\n"
            f"\"{result.transcript}\"\n\n"
            f"Key Talking Points:\n"
            + "\n".join(f"- {pt}" for pt in result.bullet_talking_points)
        )

        return AgentResponse(
            success=True,
            content=content,
            model_used="template (no TTS backend)",
            response_time=duration,
            tokens_used=0,
        )

    def synthesize_voice_commentary(self, topic_or_code: str) -> VoiceCommentaryResult:
        """Draft talking points for a topic. No model is called and no audio
        is synthesized: the transcript is a starting script, not a report on
        work done."""
        start = time.perf_counter()

        talking_points = [
            f"Suggested opening: what {topic_or_code[:40]} is for",
            "Suggested middle: the main design choice and its tradeoff",
            "Suggested close: what is still unverified",
        ]

        transcript = (
            f"Draft script for {topic_or_code}. Nothing here describes work "
            "that was done: no system was built, no tests were run, and no "
            "audio was recorded. Fill in the real design before reading this aloud."
        )

        words = len(transcript.split())
        audio_sec = round(words / 2.5, 1)  # ~150 words per minute
        duration_ms = (time.perf_counter() - start) * 1000

        return VoiceCommentaryResult(
            topic=topic_or_code,
            transcript=transcript,
            audio_duration_estimate_sec=audio_sec,
            cadence="conversational-technical",
            bullet_talking_points=talking_points,
            generation_time_ms=round(duration_ms, 2),
        )


voice_architect = VoiceArchitectAgent()
