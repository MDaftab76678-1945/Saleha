"""VoiceArchitectAgent: a spoken walkthrough of code or a topic, written by the model and checked.

The model writes a script to be read aloud. Checks: it fits the requested
length (spoken at 150 words a minute); when code was given, every function
or class it names exists in that code (no invented API); and it has talking
points. When asked for audio and pyttsx3 is installed, the script is
rendered to a WAV file -- otherwise the result says no audio was made.
"""

from __future__ import annotations

import ast
import importlib
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import AgentResponse, BaseAgent

WORDS_PER_SECOND = 2.5          # 150 words a minute


@dataclass
class VoiceCommentaryResult:
    """A script to be spoken, and the audio when it was made."""
    topic: str
    transcript: str
    audio_duration_estimate_sec: float
    cadence: str
    bullet_talking_points: List[str]
    generation_time_ms: float
    model_used: str = ""
    from_template: bool = True
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None
    audio_path: str = ""             # empty: no audio was made


def code_names(code: str) -> Set[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def script_checks(script: str, points: List[str], target_sec: Tuple[int, int], names: Set[str]) -> List[ac.Check]:
    sec = len(script.split()) / WORDS_PER_SECOND
    lo, hi = target_sec
    checks = [ac.Check("length fits", ac.PASS if lo <= sec <= hi else ac.FAIL,
                       f"{sec:.0f}s spoken, wanted {lo}-{hi}s"),
              ac.Check("talking points", ac.PASS if len(points) >= 2 else ac.FAIL, f"{len(points)} point(s)")]
    if names:
        mentioned = set(re.findall(r"`?\b([A-Za-z_][A-Za-z0-9_]*)\(\)`?", script))
        invented = sorted(mentioned - names)
        checks.append(ac.Check("names only real functions", ac.FAIL if invented else ac.PASS,
                               f"not in the code: {invented}" if invented else f"{len(mentioned)} mentioned"))
    return checks


def render_audio(text: str, path: str) -> ac.Check:
    try:
        tts = importlib.import_module("pyttsx3")
    except ImportError:
        return ac.Check("audio rendered", ac.NOT_RUN, "pyttsx3 is not installed")
    try:
        engine = tts.init()
        engine.save_to_file(text, path)
        engine.runAndWait()
    except Exception as exc:          # driver errors vary by platform
        return ac.Check("audio rendered", ac.FAIL, f"{type(exc).__name__}: {exc}")
    ok = os.path.isfile(path) and os.path.getsize(path) > 0
    return ac.Check("audio rendered", ac.PASS if ok else ac.FAIL, path if ok else "no audio file was written")


class VoiceArchitectAgent(BaseAgent):
    """Writes a spoken walkthrough with the model and checks it against the code it is about."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Voice Architect & Spoken Pair Programmer", model=model)
        self.name = "VoiceArchitectAgent"

    def execute(self, prompt: str, **kwargs) -> AgentResponse:
        start = time.perf_counter()
        r = self.synthesize_voice_commentary(prompt)
        content = (f"[VoiceArchitectAgent] {'Draft' if r.from_template else 'Script'} for: \"{r.topic[:60]}\" "
                   f"({r.audio_duration_estimate_sec}s spoken; {'audio: ' + r.audio_path if r.audio_path else 'no audio made'})\n\n"
                   f"{r.transcript}\n\nKey Talking Points:\n" + "\n".join(f"- {p}" for p in r.bullet_talking_points))
        return AgentResponse(success=True, content=content, model_used=r.model_used,
                             response_time=time.perf_counter() - start, tokens_used=0)

    def synthesize_voice_commentary(self, topic_or_code: str, seconds: Tuple[int, int] = (45, 150),
                                    audio_path: str = "") -> VoiceCommentaryResult:
        """A checked script; audio too when `audio_path` is given and a TTS engine exists."""
        start = time.perf_counter()
        names = code_names(topic_or_code)
        about = "this code" if names else "this topic"
        prompt = (f"Write a script to be read aloud, walking a developer through {about}:\n\n{topic_or_code[:6000]}\n\n"
                  f"It must take {seconds[0]}-{seconds[1]} seconds to say (about {int(seconds[0] * WORDS_PER_SECOND)}-"
                  f"{int(seconds[1] * WORDS_PER_SECOND)} words). Plain spoken sentences, no markdown in the script. "
                  + ("Name only functions and classes that are in the code, written like name(). " if names else "")
                  + "After the script, a line 'POINTS:' and 3 short talking points, one per line starting with '- '.")

        def build(content: str) -> Tuple[Tuple[str, List[str]], List[ac.Check]]:
            script, _sep, tail = content.partition("POINTS:")
            points = [ln.strip("-* \t") for ln in tail.splitlines() if ln.strip().startswith(("-", "*"))]
            script = " ".join(script.replace("**", "").split())
            return (script, points), script_checks(script, points, seconds, names)

        got, checks, resp, _rounds = ac.produce(self, prompt, build)
        # A script that still fails its checks is not read aloud: one naming
        # functions the code lacks would mislead whoever listens.
        from_template = got is None or not got[0] or ac.verdict(checks) is False
        if from_template:
            checks = ac.fallback_note(checks, got is not None)
            script = (f"Draft script for {topic_or_code[:60]}. No model wrote this: fill in the real walkthrough "
                      "before reading it aloud.")
            points = [f"What {topic_or_code[:40]} is for", "The main design choice and its tradeoff",
                      "What is still unverified"]
        else:
            script, points = got
        if audio_path and not from_template:
            checks = checks + [render_audio(script, audio_path)]
        audio_ok = any(c.name == "audio rendered" and c.status == ac.PASS for c in checks)
        return VoiceCommentaryResult(
            topic=topic_or_code[:200], transcript=script,
            audio_duration_estimate_sec=round(len(script.split()) / WORDS_PER_SECOND, 1),
            cadence="conversational-technical", bullet_talking_points=points,
            generation_time_ms=round((time.perf_counter() - start) * 1000, 2),
            model_used="template (no usable model answer)" if from_template else resp.model_used,
            from_template=from_template, checks=ac.as_dicts(checks),
            verified=None if from_template else ac.artifact_verdict(
                [c for c in checks if c.name != "audio rendered"]),
            audio_path=audio_path if audio_ok else "")


voice_architect = VoiceArchitectAgent()
