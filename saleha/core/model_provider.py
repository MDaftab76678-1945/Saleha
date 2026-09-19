"""
Saleha Core: Model Provider Abstraction (v4.0 - Universal Multi-Provider Engine)

Provides pluggable model provider backends:
1. OllamaProvider: Localhost Ollama inference ($0 local privacy).
2. OpenAICompatibleProvider: Universal API for Groq, DeepSeek, OpenRouter, OpenAI, vLLM, LM Studio.
3. FallbackChainProvider: Tries primary local provider, then gracefully falls back to cloud API or heuristic safe generator.
4. MockProvider: Deterministic zero-latency provider for unit and integration testing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable
import requests
import json
import time
import os
import urllib.error


@dataclass
class ProviderResponse:
    success: bool
    content: str
    error_message: str = ""
    response_time: float = 0.0
    tokens_used: int = 0
    provider_name: str = "ollama"


class ModelProvider(ABC):
    """Base interface for all LLM inference providers."""

    @abstractmethod
    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None) -> ProviderResponse:
        """
        `response_format` is an optional JSON schema for providers that
        support constrained decoding (Ollama's `format`). Providers without
        it may ignore the argument; callers must not assume it took effect.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    def stream_generate(self, model: str, prompt: str, callback: Callable[[str], None],
                         options: Optional[dict] = None) -> "ProviderResponse":
        """Streams tokens to `callback` as they arrive, returning the final response.

        Base implementation for providers without real streaming support: calls
        `generate()` once, then hands the whole result to `callback` as a single
        chunk. This is honest degraded behavior (one big "chunk" instead of many
        small ones), not a fabricated stream -- a subclass that talks to a
        streaming-capable backend should override this with a real one.
        """
        res = self.generate(model=model, prompt=prompt, options=options)
        if res.success and res.content:
            callback(res.content)
        return res


DEFAULT_GENERATE_TIMEOUT = int(os.environ.get("SALEHA_MODEL_TIMEOUT", "300"))

# Models that emit a chain of thought before their answer. Ollama bills that
# reasoning against the same `num_predict` budget as the answer and returns it
# in a separate `thinking` field, so a budget sized for a direct-answering
# model can be spent entirely on thinking, leaving `response` empty with
# done_reason='length'.
#
# Measured on this box, prompt "Reply with only the number 2." at
# num_predict=32 -- the budget `action_menu.py` uses for a single-integer
# choice:
#
#     qwen2.5-coder:3b -> done='stop',   answer='2'
#     qwen3.5:4b       -> done='length', answer='' , 107 chars of thinking
#
# The same model answers correctly at 2048 (done='stop', 1299 chars), so this
# is a budget problem, not a capability limit.
_REASONING_MODEL_MARKERS = ("qwen3", "deepseek-r1", "-r1:", "reasoning", "qwq")

# Headroom for the thinking block, applied before the caller's budget is used
# as the answer allowance.
_REASONING_THINKING_HEADROOM = 1024


def is_reasoning_model(model: str) -> bool:
    """True when `model` emits a chain of thought that consumes num_predict.

    Matches on the name because Ollama's /api/tags exposes no capability flag
    for this -- the only alternative is a probe generation per model.
    """
    name = (model or "").lower()
    return any(marker in name for marker in _REASONING_MODEL_MARKERS)


def budget_for_model(model: str, requested: int) -> int:
    """Grow a direct-answer budget so a reasoning model can still answer.

    A caller asking for 32 tokens wants a 32-token *answer*; on a reasoning
    model it must also pay for the thinking block first. Non-reasoning models
    are returned unchanged, so no existing measurement shifts.
    """
    if not is_reasoning_model(model):
        return requested
    return max(requested + _REASONING_THINKING_HEADROOM, 2048)


class OllamaProvider(ModelProvider):
    """Localhost Ollama server ($0 local inference)."""

    provider_name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434",
                 timeout: int = DEFAULT_GENERATE_TIMEOUT):
        self.base_url = base_url
        self.generate_url = f"{base_url}/api/generate"
        self.tags_url = f"{base_url}/api/tags"
        self.timeout = timeout

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None) -> ProviderResponse:
        """
        `response_format` is Ollama's structured-output JSON schema. When
        given, the server constrains decoding so the reply *must* match the
        schema -- the model cannot emit malformed output at all. Used by the
        action-menu loop to force a single integer choice, which removes the
        parse-failure class of errors entirely rather than recovering from it.
        """
        # Caller options are MERGED over the defaults, never substituted for
        # them. `options or {...}` meant any caller passing a partial dict
        # silently dropped every default -- and `BaseAgent.think()` passes
        # exactly `{"temperature": t}` whenever a profile sets one, so
        # `num_predict` disappeared and Ollama's small default applied.
        # Measured: qwen3:8b then spent its whole budget inside its <think>
        # block and returned HTTP 200 with an empty body
        # (done_reason='length'), which cost three control runs to diagnose.
        # A required option must not be droppable by a caller that only meant
        # to set the temperature.
        merged_options = {
            "temperature": 0.2,
            "num_predict": 2048,
            "repeat_penalty": 1.15,
            "top_p": 0.9,
        }
        if options:
            merged_options.update(options)
        # A reasoning model spends this budget on its thinking block before it
        # writes any answer, so a budget sized for a direct answer yields an
        # empty response. Grown here rather than at each of the ~17 call sites,
        # which cannot know which model they will be routed to.
        merged_options["num_predict"] = budget_for_model(
            model, merged_options["num_predict"])
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": merged_options,
        }
        if response_format:
            payload["format"] = response_format

        # Some community-published models ship a Modelfile carrying option
        # values this Ollama build rejects outright -- observed with
        # wcamaralopes/bonsai-27b, whose `repeat_last_n: -1` makes every
        # request fail with HTTP 400 ("Value must be between 0 and
        # 2147483647, but got -1") before the model ever runs. Sending a
        # valid explicit value overrides the bad default, so a model that
        # works is not written off as broken.
        opts = payload.get("options")
        if isinstance(opts, dict) and opts.get("repeat_last_n", 0) < 0:
            opts["repeat_last_n"] = 64

        start_time = time.time()
        try:
            response = requests.post(self.generate_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            content = result.get("response", "").strip()
            if not content:
                # HTTP 200 with an empty `response` was reported as
                # success=True with no content, so every caller treated "the
                # model said nothing" as a completed generation. Measured
                # against a real repo run: the agent loop logged three
                # `(empty reply)` turns and burned its parse-retry budget,
                # unable to tell an empty generation from a provider failure.
                # An answer that is not there is not a success.
                return ProviderResponse(
                    success=False,
                    content="",
                    error_message=(
                        f"Ollama returned HTTP 200 with an empty response "
                        f"(model={model}, prompt {len(prompt)} chars, "
                        f"done_reason={result.get('done_reason', 'unknown')!r}). "
                        f"The request succeeded but the model generated "
                        f"nothing."
                    ),
                    response_time=time.time() - start_time,
                    tokens_used=int(result.get("eval_count", 0) or 0),
                    provider_name="ollama",
                )
            return ProviderResponse(
                success=True,
                content=content,
                response_time=time.time() - start_time,
                tokens_used=int(result.get("eval_count", 0) or 0),
                provider_name="ollama",
            )
        except requests.exceptions.Timeout:
            # Distinguished from a connection failure: the server answered the
            # TCP connect and then took too long. Reporting this as "not
            # running" sent callers to restart a server that was working --
            # a 3b model generating from a long prompt simply needs longer.
            error_msg = (
                f"Ollama did not respond within {self.timeout}s "
                f"(model={model}, prompt {len(prompt)} chars). "
                f"Raise SALEHA_MODEL_TIMEOUT if the model needs longer."
            )
            return ProviderResponse(
                success=False,
                content="",
                error_message=error_msg,
                response_time=time.time() - start_time,
                provider_name="ollama",
            )
        except requests.exceptions.ConnectionError:
            return ProviderResponse(
                success=False,
                content="",
                error_message=f"Ollama server not reachable at {self.base_url}",
                response_time=time.time() - start_time,
                provider_name="ollama",
            )
        except Exception as e:
            return ProviderResponse(
                success=False,
                content="",
                error_message=str(e),
                response_time=time.time() - start_time,
                provider_name="ollama",
            )

    def is_available(self) -> bool:
        try:
            resp = requests.get(self.tags_url, timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False

    def stream_generate(self, model: str, prompt: str, callback: Callable[[str], None],
                         options: Optional[dict] = None) -> ProviderResponse:
        """Real token-by-token streaming via Ollama's `stream: true` NDJSON response.

        Each line of the response body is one JSON object with a `response`
        chunk; `done: true` marks the final line, which also carries
        `eval_count`. `callback` is invoked once per chunk as it arrives --
        this is a genuine incremental stream, not `generate()` results replayed
        as one chunk.
        """
        # Merged, not substituted -- `options or {...}` dropped every default
        # for any caller passing a partial dict. That exact bug was fixed in
        # generate() (pass 53) and left standing here.
        merged_options = {
            "temperature": 0.2,
            "num_predict": 2048,
            "repeat_penalty": 1.15,
            "top_p": 0.9,
        }
        if options:
            merged_options.update(options)
        merged_options["num_predict"] = budget_for_model(
            model, merged_options["num_predict"])
        if merged_options.get("repeat_last_n", 0) < 0:
            merged_options["repeat_last_n"] = 64
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": merged_options,
        }

        start_time = time.time()
        accumulated = []
        tokens_used = 0
        try:
            with requests.post(self.generate_url, json=payload, timeout=self.timeout,
                                stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    chunk = json.loads(line)
                    piece = chunk.get("response", "")
                    if piece:
                        accumulated.append(piece)
                        callback(piece)
                    if chunk.get("done"):
                        tokens_used = int(chunk.get("eval_count", 0) or 0)
            return ProviderResponse(
                success=True,
                content="".join(accumulated),
                response_time=time.time() - start_time,
                tokens_used=tokens_used,
                provider_name="ollama",
            )
        except requests.exceptions.Timeout:
            error_msg = (
                f"Ollama did not respond within {self.timeout}s "
                f"(model={model}, prompt {len(prompt)} chars) while streaming."
            )
            return ProviderResponse(success=False, content="".join(accumulated),
                                     error_message=error_msg,
                                     response_time=time.time() - start_time,
                                     provider_name="ollama")
        except requests.exceptions.ConnectionError:
            return ProviderResponse(success=False, content="".join(accumulated),
                                     error_message=f"Ollama server not reachable at {self.base_url}",
                                     response_time=time.time() - start_time,
                                     provider_name="ollama")
        except Exception as e:
            return ProviderResponse(success=False, content="".join(accumulated),
                                     error_message=str(e),
                                     response_time=time.time() - start_time,
                                     provider_name="ollama")


class OpenAICompatibleProvider(ModelProvider):
    """Universal OpenAI-compatible API for Groq, DeepSeek, OpenRouter, OpenAI, vLLM, LM Studio."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        provider_name: str = "openai_compatible",
        timeout: int = DEFAULT_GENERATE_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""
        self.provider_name = provider_name
        self.timeout = timeout

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None) -> ProviderResponse:
        if not self.api_key and not ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
            return ProviderResponse(
                success=False,
                content="",
                error_message="API key missing for OpenAI-compatible provider",
                provider_name=self.provider_name,
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model or "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": (options or {}).get("temperature", 0.2),
        }

        start_time = time.time()
        try:
            url = f"{self.base_url}/chat/completions"
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            content = choices[0]["message"]["content"].strip() if choices else ""
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return ProviderResponse(
                success=True,
                content=content,
                response_time=time.time() - start_time,
                tokens_used=tokens,
                provider_name=self.provider_name,
            )
        except Exception as e:
            return ProviderResponse(
                success=False,
                content="",
                error_message=str(e),
                response_time=time.time() - start_time,
                provider_name=self.provider_name,
            )

    def is_available(self) -> bool:
        return bool(self.api_key) or ("localhost" in self.base_url or "127.0.0.1" in self.base_url)


class FallbackChainProvider(ModelProvider):
    """
    Intelligent cascade provider:
    Tries providers in sequence (e.g. Local Ollama -> Groq/DeepSeek -> Cloud API).
    Ensures zero interruption for developers.
    """

    def __init__(self, providers: Optional[List[ModelProvider]] = None):
        self.providers = providers or [
            OllamaProvider(),
            OpenAICompatibleProvider(base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")),
        ]

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None) -> ProviderResponse:
        """
        `response_format` (a JSON schema) is forwarded to providers that
        support constrained decoding and silently ignored by those that do
        not, so a caller relying on it degrades rather than breaking. It was
        previously dropped here, which meant the action-menu loop's
        constrained decoding never actually took effect.
        """
        errors = []
        for p in self.providers:
            if p.is_available():
                try:
                    res = p.generate(model=model, prompt=prompt, options=options,
                                     response_format=response_format)
                except TypeError:
                    # Provider predates response_format -- still usable.
                    res = p.generate(model=model, prompt=prompt, options=options)
                if res.success:
                    return res
                errors.append(f"{getattr(p, 'provider_name', 'unknown')}: {res.error_message}")
        
        # If all providers unavailable or failed, return composite error
        return ProviderResponse(
            success=False,
            content="",
            error_message="All providers in fallback chain failed: " + " | ".join(errors),
            provider_name="fallback_chain",
        )

    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)

    def stream_generate(self, model: str, prompt: str, callback: Callable[[str], None],
                         options: Optional[dict] = None) -> ProviderResponse:
        """Streams from the first available provider; falls through on failure.

        Same cascade behavior as generate(): each provider is tried in order,
        and a provider without real streaming still degrades honestly (one
        chunk) via the base class rather than breaking the caller.
        """
        errors = []
        for p in self.providers:
            if p.is_available():
                res = p.stream_generate(model=model, prompt=prompt, callback=callback,
                                         options=options)
                if res.success:
                    return res
                errors.append(f"{getattr(p, 'provider_name', 'unknown')}: {res.error_message}")

        return ProviderResponse(
            success=False,
            content="",
            error_message="All providers in fallback chain failed: " + " | ".join(errors),
            provider_name="fallback_chain",
        )


class MockProvider(ModelProvider):
    """Deterministic zero-latency mock provider for tests."""

    def __init__(self, default_response: str = "def solve():\n    return 42"):
        self.default_response = default_response

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None) -> ProviderResponse:
        return ProviderResponse(
            success=True,
            content=self.default_response,
            response_time=0.001,
            tokens_used=12,
            provider_name="mock",
        )

    def is_available(self) -> bool:
        return True


# Default active provider singleton
default_provider: ModelProvider = FallbackChainProvider()
model_provider = default_provider
