"""
Saleha Agents: Base Agent (v3.1 - Model Provider Abstraction)

Naya vs pehle: Ollama se seedha baat karne ke bajaye ab `model_provider.py`
ke through hota hai. Behavior bilkul same hai (same URL, same payload,
same timeout) -- sirf ye ki agar kabhi backend badalna ho, sirf
model_provider.py me naya provider likhna hoga, ye file chhedni nahi padegi.
"""
import uuid
import time
from dataclasses import dataclass
from typing import Optional
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from saleha.core.smart_router import SmartRouter
from saleha.core.model_provider import default_provider, ModelProvider


@dataclass
class AgentResponse:
    success: bool
    content: str
    error_message: str = ""
    model_used: str = ""
    response_time: float = 0.0
    tokens_used: int = 0


class BaseAgent:
    def __init__(self, role: str, model: str = "auto", provider: Optional[ModelProvider] = None):
        self.role = role
        self.model_preference = model
        self.provider = provider or default_provider  # naya: pluggable backend
        self.task_counter = 0
        # "auto" mode me runtime Ollama probing enable -- router sirf installed
        # models choose karta hai (2026 catalog + adaptive candidate filtering).
        self.router = SmartRouter(probe_runtime=True) if model == "auto" else None
        self.total_tokens_used = 0  # v1.2: agent-lifetime token accounting

    def _record_tokens(self, provider_result) -> int:
        used = int(getattr(provider_result, "tokens_used", 0) or 0)
        self.total_tokens_used += used
        return used

    def think(self, prompt: str, previous_error_reflexion: Optional[str] = None,
              complexity_score: float = 0.0) -> AgentResponse:
        self.task_counter += 1
        start_time = time.time()

        # Smart model selection
        if self.model_preference == "auto" and self.router:
            selected_model = self.router.select_model(prompt, complexity_score)
        else:
            selected_model = self.model_preference

        unique_task_id = f"TASK-{uuid.uuid4().hex[:8]}-{self.task_counter}"
        full_prompt = f"[UNIQUE TASK ID: {unique_task_id}]\n\n{prompt}"
        if previous_error_reflexion:
            full_prompt += f"\n\n[SALEHA SELF-HEALING INSTRUCTION]:\n{previous_error_reflexion}"

        provider_result = self.provider.generate(model=selected_model, prompt=full_prompt)
        response_time = provider_result.response_time or (time.time() - start_time)

        if self.router:
            self.router.record_result(
                prompt, complexity_score, selected_model,
                response_time, provider_result.success
            )

        if provider_result.success:
            return AgentResponse(
                success=True,
                content=provider_result.content,
                model_used=selected_model,
                response_time=response_time,
                tokens_used=self._record_tokens(provider_result),
            )
        else:
            return AgentResponse(
                success=False,
                content="",
                error_message=provider_result.error_message,
                model_used=selected_model,
                response_time=response_time,
            )

    def think_stream(self, prompt: str, on_token=None,
                     previous_error_reflexion: Optional[str] = None,
                     complexity_score: float = 0.0) -> AgentResponse:
        """Token-level real-time streaming variant of think().

        `on_token(str)` har token chunk par fire hota hai (Ollama NDJSON
        stream). Response poora hoke wahi AgentResponse milti hai -- callers
        tokens live print kar sakte hain bina downstream logic badle.

        Provider stream support na kare to silently non-streaming generate
        pe fallback (graceful degradation).
        """
        self.task_counter += 1
        start_time = time.time()

        if self.model_preference == "auto" and self.router:
            selected_model = self.router.select_model(prompt, complexity_score)
        else:
            selected_model = self.model_preference

        unique_task_id = f"TASK-{uuid.uuid4().hex[:8]}-{self.task_counter}"
        full_prompt = f"[UNIQUE TASK ID: {unique_task_id}]\n\n{prompt}"
        if previous_error_reflexion:
            full_prompt += f"\n\n[SALEHA SELF-HEALING INSTRUCTION]:\n{previous_error_reflexion}"

        stream_fn = getattr(self.provider, "stream_generate", None)
        if callable(stream_fn):
            provider_result = stream_fn(model=selected_model, prompt=full_prompt, callback=on_token)
        else:
            provider_result = self.provider.generate(model=selected_model, prompt=full_prompt)

        response_time = provider_result.response_time or (time.time() - start_time)

        if self.router:
            self.router.record_result(
                prompt, complexity_score, selected_model,
                response_time, provider_result.success
            )

        if provider_result.success:
            return AgentResponse(
                success=True,
                content=provider_result.content,
                model_used=selected_model,
                response_time=response_time,
                tokens_used=self._record_tokens(provider_result),
            )
        return AgentResponse(
            success=False,
            content="",
            error_message=provider_result.error_message,
            model_used=selected_model,
            response_time=response_time,
        )