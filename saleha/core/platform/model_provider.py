"""
Saleha Core: Model Provider Abstraction (v4.0 - Universal Multi-Provider Engine)

Provides pluggable model provider backends:
1. OllamaProvider: Localhost Ollama inference ($0 local privacy).
2. OpenAICompatibleProvider: Universal API for Groq, DeepSeek, OpenRouter, OpenAI, vLLM, LM Studio.
3. ClaudeCodeProvider: Claude through the local Claude Code CLI (`claude -p`),
   using the user's own subscription login -- no API key. Selected by model
   names starting with "claude-code" (e.g. "claude-code:sonnet").
   GeminiProvider: Google Gemini API with a GEMINI_API_KEY (free AI Studio
   key). Selected by model names starting with "gemini" (e.g. "gemini",
   "gemini:gemini-3.5-flash", "gemini-2.5-pro").
4. FallbackChainProvider: Tries primary local provider, then gracefully falls back to cloud API or heuristic safe generator.
5. MockProvider: Deterministic zero-latency provider for unit and integration testing.

Cloud is never used for a run with SALEHA_LOCAL_ONLY=1: the provider refuses
and says so rather than falling back silently.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

import requests

from saleha.core.platform.circuit_breaker import (
    Admission,
    CircuitBreaker,
    CircuitState,
    Health,
    classify_status,
    shared_breaker,
)
from saleha.core.platform.ollama_endpoint import ollama_base_url


@dataclass
class ProviderResponse:
    success: bool
    content: str
    error_message: str = ""
    response_time: float = 0.0
    tokens_used: int = 0
    provider_name: str = "ollama"
    # List-price cost the backend reported for this call (0.0 when unknown or
    # free). For Claude Code on a subscription this is notional, not billed.
    cost_usd: float = 0.0


class ModelProvider(ABC):
    """Base interface for all LLM inference providers."""

    @abstractmethod
    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        """
        `response_format` is an optional JSON schema for providers that
        support constrained decoding (Ollama's `format`). Providers without
        it may ignore the argument; callers must not assume it took effect.

        `disable_reasoning` asks a reasoning-capable provider to skip its
        chain-of-thought entirely. Providers with no such concept (or no
        way to disable it) may ignore this argument.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    def unavailable_reason(self) -> str:
        """Why is_available() said no, for the caller's error message."""
        return "not available"

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


def _health_of(exc: Exception) -> Health:
    """What a failed Ollama call says about the server (see circuit_breaker.Health)."""
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(exc.response, "status_code", None)
        return classify_status(status)[0] if isinstance(status, int) else Health.UNHEALTHY
    if isinstance(exc, (ValueError, OSError)):  # a malformed body, or the transport
        return Health.UNHEALTHY
    return Health.UNKNOWN


class OllamaProvider(ModelProvider):
    """
    Local Ollama server ($0 local inference).

    Calls go through the process-wide circuit breaker, keyed by base URL:
    after SALEHA_BREAKER_FAILURES consecutive failures (refused, timed out,
    5xx) the provider answers "not called" at once for
    SALEHA_BREAKER_OPEN_SECONDS, then lets one call through to test the
    server. A 4xx or an empty answer proves the server is up and does not
    count against it.
    """

    provider_name = "ollama"

    def __init__(self, base_url: Optional[str] = None,
                 timeout: int = DEFAULT_GENERATE_TIMEOUT,
                 breaker: Optional[CircuitBreaker] = None):
        # SALEHA_OLLAMA_URL / OLLAMA_HOST, normalised. The hard-coded
        # `localhost` default ignored both, and a refused connection through
        # `localhost` costs ~4 s here against ~2 s for 127.0.0.1 (both
        # addresses are tried).
        self.base_url = (base_url or ollama_base_url()).rstrip("/")
        self.generate_url = f"{self.base_url}/api/generate"
        self.tags_url = f"{self.base_url}/api/tags"
        self.timeout = timeout
        self.breaker = breaker or shared_breaker()

    def _not_called(self, admission: Admission) -> ProviderResponse:
        wait = f"; next try in {admission.retry_after:.0f}s" if admission.retry_after else ""
        return ProviderResponse(False, "", f"Ollama at {self.base_url} not called: {admission.reason}{wait}",
                                provider_name="ollama")

    def unavailable_reason(self) -> str:
        snap = self.breaker.snapshot(self.base_url)
        if snap.state is not CircuitState.CLOSED:
            return f"circuit {snap.state.value} after {snap.failures} failure(s): {snap.last_error}"
        return f"no answer from {self.tags_url}"

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        """
        `response_format` is Ollama's structured-output JSON schema. When
        given, the server constrains decoding so the reply *must* match the
        schema -- the model cannot emit malformed output at all. Used by the
        action-menu loop to force a single integer choice, which removes the
        parse-failure class of errors entirely rather than recovering from it.

        `disable_reasoning=True` sends Ollama's top-level `think: false`,
        which turns off a reasoning model's <think> block entirely rather
        than budgeting around it. Measured on this box (qwen3:8b, the same
        planted `requests` bug from pass 85-86): with reasoning left on, a
        571-char prompt took 140.4s for the correct patch; with
        `think: false`, the same prompt took 9.0s for the same correct
        patch, done_reason='stop' instead of racing a token budget. Callers
        that want a structured action (a tool_call, not an explanation)
        should pass this -- `_REASONING_THINKING_HEADROOM` below is a
        budget guess for callers that still want the reasoning; this is
        an actual measured fix for callers that do not.
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
        if disable_reasoning:
            # Turning thinking off outright beats budgeting around it: no
            # token competition, no risk of an empty done_reason='length'
            # reply, and the caller's own num_predict is left alone.
            payload: dict = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": merged_options,
            }
        else:
            # A reasoning model spends this budget on its thinking block
            # before it writes any answer, so a budget sized for a direct
            # answer yields an empty response. Grown here rather than at
            # each of the ~17 call sites, which cannot know which model
            # they will be routed to.
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

        admission = self.breaker.admit(self.base_url)
        if not admission.allowed:
            return self._not_called(admission)
        health, detail = Health.UNKNOWN, "call did not finish"
        start_time = time.time()
        try:
            response = requests.post(self.generate_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            health, detail = Health.HEALTHY, ""
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
            health, detail = Health.UNHEALTHY, f"no answer within {self.timeout}s"
            return ProviderResponse(
                success=False,
                content="",
                error_message=error_msg,
                response_time=time.time() - start_time,
                provider_name="ollama",
            )
        except requests.exceptions.ConnectionError:
            health, detail = Health.UNHEALTHY, f"not reachable at {self.base_url}"
            return ProviderResponse(
                success=False,
                content="",
                error_message=f"Ollama server not reachable at {self.base_url}",
                response_time=time.time() - start_time,
                provider_name="ollama",
            )
        except Exception as e:
            health, detail = _health_of(e), str(e)[:200]
            return ProviderResponse(
                success=False,
                content="",
                error_message=str(e),
                response_time=time.time() - start_time,
                provider_name="ollama",
            )
        finally:
            self.breaker.record(self.base_url, admission, health, detail)

    def is_available(self) -> bool:
        """
        A real GET /api/tags, skipped while the circuit is open. A reachable
        server says nothing about whether generation works (tags answer
        while a generation hangs), so a success only hands back a probe
        slot for generate() to use; a failure counts against the server.
        """
        admission = self.breaker.admit(self.base_url)
        if not admission.allowed:
            return False
        health, detail = Health.UNKNOWN, ""
        try:
            resp = requests.get(self.tags_url, timeout=1.5)
            if resp.status_code != 200:
                health, detail = Health.UNHEALTHY, f"GET /api/tags returned HTTP {resp.status_code}"
            return resp.status_code == 200
        except Exception as exc:
            health, detail = Health.UNHEALTHY, f"GET /api/tags failed: {type(exc).__name__}"
            return False
        finally:
            self.breaker.record(self.base_url, admission, health, detail)

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

        admission = self.breaker.admit(self.base_url)
        if not admission.allowed:
            return self._not_called(admission)
        health, detail = Health.UNKNOWN, "call did not finish"
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
            health, detail = Health.HEALTHY, ""
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
            health, detail = Health.UNHEALTHY, f"no answer within {self.timeout}s while streaming"
            return ProviderResponse(success=False, content="".join(accumulated),
                                     error_message=error_msg,
                                     response_time=time.time() - start_time,
                                     provider_name="ollama")
        except requests.exceptions.ConnectionError:
            health, detail = Health.UNHEALTHY, f"not reachable at {self.base_url}"
            return ProviderResponse(success=False, content="".join(accumulated),
                                     error_message=f"Ollama server not reachable at {self.base_url}",
                                     response_time=time.time() - start_time,
                                     provider_name="ollama")
        except Exception as e:
            health, detail = _health_of(e), str(e)[:200]
            return ProviderResponse(success=False, content="".join(accumulated),
                                     error_message=str(e),
                                     response_time=time.time() - start_time,
                                     provider_name="ollama")
        finally:
            self.breaker.record(self.base_url, admission, health, detail)


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
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        # No known OpenAI-compatible endpoint exposes a "disable
        # chain-of-thought" switch through this API shape, so the flag is
        # accepted for interface parity and otherwise has no effect here.
        if local_only() and not self._is_local():
            # This provider sits in the default fallback chain: without this
            # check a failed local call fell through to api.openai.com
            # whenever OPENAI_API_KEY/GROQ_API_KEY was set.
            return ProviderResponse(False, "", "cloud disabled: SALEHA_LOCAL_ONLY=1",
                                    provider_name=self.provider_name)
        if not self.api_key and not self._is_local():
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

    def _is_local(self) -> bool:
        """True for an endpoint on this machine (LM Studio, vLLM, llama.cpp server)."""
        from urllib.parse import urlparse
        host = (urlparse(self.base_url).hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")

    def is_available(self) -> bool:
        if self._is_local():
            return True
        return bool(self.api_key) and not local_only()


CLAUDE_CODE_PREFIX = "claude-code"


def local_only() -> bool:
    """True when this run must not send anything to a cloud model."""
    return os.environ.get("SALEHA_LOCAL_ONLY") == "1"


class ClaudeCodeProvider(ModelProvider):
    """Claude via the Claude Code CLI in print mode, on the user's own login.

    Runs `claude -p --output-format json --tools ""` with the prompt on stdin
    (Windows command lines cap at ~32K chars), in an empty temp directory so
    no project CLAUDE.md is pulled into the call, and with every tool
    disabled: this is text generation only, never a second agent acting on
    the machine.

    Model names: "claude-code" (the CLI's default) or "claude-code:<model>",
    e.g. "claude-code:sonnet", "claude-code:opus", "claude-code:haiku".
    """

    provider_name = "claude_code"

    def __init__(self, timeout: int = DEFAULT_GENERATE_TIMEOUT, executable: Optional[str] = None):
        self.timeout = timeout
        # None means "find it"; "" means "treat as not installed" (tests).
        self.executable = shutil.which("claude") if executable is None else executable

    @staticmethod
    def cli_model(model: str) -> str:
        """"claude-code:sonnet" -> "sonnet"; "claude-code" -> "" (CLI default)."""
        rest = (model or "")[len(CLAUDE_CODE_PREFIX):]
        return rest[1:] if rest.startswith((":", "/")) else ""

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        if local_only():
            return ProviderResponse(False, "", "cloud disabled: SALEHA_LOCAL_ONLY=1",
                                    provider_name=self.provider_name)
        if not self.executable:
            return ProviderResponse(False, "", "Claude Code CLI (`claude`) not found on PATH",
                                    provider_name=self.provider_name)
        argv = [self.executable, "-p", "--output-format", "json", "--tools", "",
                "--no-session-persistence", "--strict-mcp-config"]
        name = self.cli_model(model)
        if name:
            argv += ["--model", name]
        start = time.time()
        try:
            with tempfile.TemporaryDirectory(prefix="saleha-claude-") as empty:
                proc = subprocess.run(argv, input=prompt, cwd=empty, capture_output=True,
                                      text=True, encoding="utf-8", errors="replace",
                                      timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return ProviderResponse(False, "", f"claude -p timed out after {self.timeout}s",
                                    response_time=time.time() - start,
                                    provider_name=self.provider_name)
        except OSError as exc:
            return ProviderResponse(False, "", f"could not run claude: {exc}",
                                    provider_name=self.provider_name)
        elapsed = time.time() - start
        try:
            data = json.loads(proc.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            detail = (proc.stderr or proc.stdout).strip()[-300:]
            return ProviderResponse(False, "", f"claude -p gave no JSON (exit {proc.returncode}): {detail}",
                                    response_time=elapsed, provider_name=self.provider_name)
        text = str(data.get("result") or "")
        if data.get("is_error") or proc.returncode != 0 or not text.strip():
            return ProviderResponse(False, "", f"claude -p error: {text[:300] or data.get('subtype', 'no result')}",
                                    response_time=elapsed, provider_name=self.provider_name)
        usage = data.get("usage") or {}
        tokens = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
        return ProviderResponse(True, text.strip(), response_time=elapsed, tokens_used=tokens,
                                provider_name=self.provider_name,
                                cost_usd=float(data.get("total_cost_usd", 0.0) or 0.0))

    def is_available(self) -> bool:
        return bool(self.executable) and not local_only()


GEMINI_PREFIX = "gemini"
GEMINI_DEFAULT_MODEL = os.environ.get("SALEHA_GEMINI_MODEL", "gemini-3.5-flash")
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def user_env(name: str) -> str:
    """An environment variable, falling back to the Windows user environment.

    A key saved in the user's Windows settings is invisible to processes
    that were already running when it was saved (the IDE, and everything it
    starts) until they restart. Reading the HKCU "Environment" registry key
    directly means the
    user does not have to restart anything.
    """
    value = os.environ.get(name, "")
    if value or os.name != "nt":
        return value
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return ""


def _gemini_retry_delay(resp: Any) -> Optional[float]:
    """Seconds a Gemini 429 asks the caller to wait (RetryInfo.retryDelay), if it says.

    A per-day quota returns infinity: measured, the free tier allows 20
    requests a day per model and still says "retryDelay: 7s", so waiting
    7 s and asking again only burns time until the day ends.
    """
    try:
        details = (resp.json().get("error") or {}).get("details") or []
    except (ValueError, AttributeError):
        return None
    for d in details:
        if isinstance(d, dict) and str(d.get("@type", "")).endswith("QuotaFailure"):
            if any("PerDay" in str(v.get("quotaId", "")) for v in d.get("violations") or []
                   if isinstance(v, dict)):
                return float("inf")
    for d in details:
        if isinstance(d, dict) and str(d.get("@type", "")).endswith("RetryInfo"):
            m = re.match(r"\s*([\d.]+)s\s*$", str(d.get("retryDelay", "")))
            if m:
                return float(m.group(1))
    return None


class GeminiProvider(ModelProvider):
    """Google Gemini through its REST API, with the user's GEMINI_API_KEY.

    The key travels only in the x-goog-api-key header -- never in the URL,
    so it cannot leak into an error message that echoes the request URL.
    """

    provider_name = "gemini"

    def __init__(self, api_key: Optional[str] = None, timeout: int = DEFAULT_GENERATE_TIMEOUT):
        self.api_key = user_env("GEMINI_API_KEY") if api_key is None else api_key
        self.timeout = timeout

    @staticmethod
    def api_model(model: str) -> str:
        """"gemini" -> default; "gemini:x" -> "x"; "gemini-2.5-pro" -> itself."""
        name = (model or "").strip()
        if name in (GEMINI_PREFIX, f"{GEMINI_PREFIX}:"):
            return GEMINI_DEFAULT_MODEL
        if name.startswith(f"{GEMINI_PREFIX}:"):
            return name.split(":", 1)[1]
        return name

    def generate(self, model: str, prompt: str, options: Optional[dict] = None,
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        if local_only():
            return ProviderResponse(False, "", "cloud disabled: SALEHA_LOCAL_ONLY=1",
                                    provider_name=self.provider_name)
        if not self.api_key:
            return ProviderResponse(False, "", "GEMINI_API_KEY is not set",
                                    provider_name=self.provider_name)
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if options and "temperature" in options:
            body["generationConfig"] = {"temperature": options["temperature"]}
        start = time.time()
        # 429 / 500 / 503 are usually momentary ("high demand" was measured
        # mid-benchmark). A per-minute quota tells how long to wait
        # (RetryInfo.retryDelay); waiting 2-6 s against a 30 s window only
        # spent the retries. A wait over a minute is a daily quota: give up.
        resp = None
        backoff = (2.0, 6.0, 20.0)
        for attempt in range(len(backoff) + 1):
            try:
                resp = requests.post(_GEMINI_URL.format(model=self.api_model(model)), json=body,
                                     headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
            except requests.RequestException as exc:
                return ProviderResponse(False, "", f"Gemini request failed: {type(exc).__name__}",
                                        response_time=time.time() - start,
                                        provider_name=self.provider_name)
            if resp.status_code not in (429, 500, 503) or attempt == len(backoff):
                break
            wait = _gemini_retry_delay(resp)
            if wait is not None and wait > 60:
                break
            time.sleep(wait if wait is not None else backoff[attempt])
        assert resp is not None  # the loop always makes at least one request
        elapsed = time.time() - start
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code != 200:
            msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
            return ProviderResponse(False, "", f"Gemini HTTP {resp.status_code}: {msg[:300]}",
                                    response_time=elapsed, provider_name=self.provider_name)
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        text = "".join(str(part.get("text", "")) for part in parts if not part.get("thought"))
        if not text.strip():
            why = ((data.get("promptFeedback") or {}).get("blockReason")
                   or (candidates[0].get("finishReason") if candidates else "no candidates"))
            return ProviderResponse(False, "", f"Gemini returned no text ({why})",
                                    response_time=elapsed, provider_name=self.provider_name)
        tokens = int((data.get("usageMetadata") or {}).get("totalTokenCount", 0) or 0)
        return ProviderResponse(True, text.strip(), response_time=elapsed, tokens_used=tokens,
                                provider_name=self.provider_name)

    def is_available(self) -> bool:
        return bool(self.api_key) and not local_only()


def cloud_provider_for(model: str) -> Optional[ModelProvider]:
    """The provider a cloud model name belongs to, or None for local models."""
    name = model or ""
    if name.startswith(CLAUDE_CODE_PREFIX):
        return ClaudeCodeProvider()
    if name.startswith(GEMINI_PREFIX):
        return GeminiProvider()
    return None


def _unavailable(provider: object) -> str:
    """A skipped provider still shows up in the chain's error: an empty list read as 'no reason'."""
    reason = provider.unavailable_reason() if isinstance(provider, ModelProvider) else "not available"
    return f"{getattr(provider, 'provider_name', 'unknown')}: skipped, {reason}"


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
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
        """
        `response_format` (a JSON schema) is forwarded to providers that
        support constrained decoding and silently ignored by those that do
        not, so a caller relying on it degrades rather than breaking. It was
        previously dropped here, which meant the action-menu loop's
        constrained decoding never actually took effect. `disable_reasoning`
        is forwarded the same way.

        A cloud model name ("claude-code:...", "gemini...") goes straight to its provider:
        sending it down the local chain would only produce Ollama "model not
        found" errors before reaching it.
        """
        cloud = cloud_provider_for(model)
        if cloud is not None:
            return cloud.generate(model=model, prompt=prompt, options=options,
                                  response_format=response_format,
                                  disable_reasoning=disable_reasoning)
        errors = []
        for p in self.providers:
            if p.is_available():
                try:
                    res = p.generate(model=model, prompt=prompt, options=options,
                                     response_format=response_format,
                                     disable_reasoning=disable_reasoning)
                except TypeError:
                    # Provider predates one of these keyword arguments -- still usable.
                    res = p.generate(model=model, prompt=prompt, options=options)
                if res.success:
                    return res
                errors.append(f"{getattr(p, 'provider_name', 'unknown')}: {res.error_message}")
            else:
                errors.append(_unavailable(p))
        
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
            else:
                errors.append(_unavailable(p))

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
                 response_format: Optional[dict] = None,
                 disable_reasoning: bool = False) -> ProviderResponse:
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
