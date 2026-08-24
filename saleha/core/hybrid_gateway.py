"""
Saleha Core: Hybrid Multi-Model Cloud Gateway

Provides a unified interface across local Ollama and optional cloud providers
(Groq, Anthropic Claude, OpenAI GPT-4o, Google Gemini, OpenRouter) with
automatic graceful fallback and token efficiency tracking.
"""

import os
import time
import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class GatewayResponse:
    content: str
    provider: str
    model: str
    latency: float
    success: bool = True
    error: str = ""
    tokens_used: int = 0


class HybridModelGateway:
    """Unified Gateway for local and cloud LLM providers."""

    PROVIDER_ENDPOINTS = {
        "ollama": "http://localhost:11434/api/generate",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "openai": "https://api.openai.com/v1/chat/completions",
        "anthropic": "https://api.anthropic.com/v1/messages",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    }

    def __init__(self, default_provider: str = "ollama"):
        self.default_provider = default_provider

    def list_available_providers(self) -> Dict[str, bool]:
        """Detects which providers have active environment keys or local service."""
        status = {
            "ollama": self._is_ollama_alive(),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        }
        return status

    def _is_ollama_alive(self) -> bool:
        try:
            req = urllib.request.Request("http://localhost:11434/api/version", method="GET")
            with urllib.request.urlopen(req, timeout=1) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def generate(self, prompt: str,
                 system_prompt: str = "You are an expert AI engineer.",
                 provider: Optional[str] = None,
                 model: Optional[str] = None,
                 temperature: float = 0.2,
                 fallback: bool = True) -> GatewayResponse:
        """Dispatches generation request to specified or optimal provider."""
        selected_provider = (provider or self.default_provider).lower()
        start_time = time.time()

        if selected_provider == "ollama":
            res = self._call_ollama(prompt, system_prompt, model or "deepseek-coder:6.7b", temperature)
            if res.success or not fallback:
                return res
            # Fallback if Ollama is unavailable
            fallback_target = self._find_first_available_cloud_provider()
            if fallback_target:
                return self.generate(prompt, system_prompt, provider=fallback_target, model=None, fallback=False)
            return res

        # OpenAI-compatible providers
        PROVIDER_DEFAULTS = {
            "groq": ("GROQ_API_KEY", "llama-3.3-70b-versatile"),
            "openai": ("OPENAI_API_KEY", "gpt-4o"),
            "openrouter": ("OPENROUTER_API_KEY", "anthropic/claude-3.5-sonnet"),
        }

        if selected_provider in PROVIDER_DEFAULTS:
            env_key, default_model = PROVIDER_DEFAULTS[selected_provider]
            return self._call_openai_compatible(
                url=self.PROVIDER_ENDPOINTS[selected_provider],
                api_key=os.getenv(env_key, ""),
                model=model or default_model,
                provider_name=selected_provider,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )

        # Anthropic Messages API (native -- Bearer-style nahi)
        if selected_provider == "anthropic":
            return self._call_anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                model=model or "claude-sonnet-4-5",
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )

        # Google Gemini generateContent API (native)
        if selected_provider == "gemini":
            return self._call_gemini(
                api_key=os.getenv("GEMINI_API_KEY", ""),
                model=model or "gemini-2.5-flash",
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )

        return GatewayResponse(
            content="",
            provider=selected_provider,
            model=model or "unknown",
            latency=time.time() - start_time,
            success=False,
            error=f"Unsupported provider: {selected_provider}"
        )

    def _call_ollama(self, prompt: str, system: str, model: str, temp: float) -> GatewayResponse:
        start = time.time()
        url = self.PROVIDER_ENDPOINTS["ollama"]
        payload = {
            "model": model,
            "prompt": f"{system}\n\nUser: {prompt}\n\nAssistant:",
            "stream": False,
            "options": {"temperature": temp}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return GatewayResponse(
                    content=data.get("response", ""),
                    provider="ollama",
                    model=model,
                    latency=time.time() - start,
                    success=True,
                    tokens_used=data.get("eval_count", 0)
                )
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            return GatewayResponse(
                content="",
                provider="ollama",
                model=model,
                latency=time.time() - start,
                success=False,
                error=f"Ollama connection error: {str(e)}"
            )

    def _call_openai_compatible(self, url: str, api_key: str, model: str,
                                provider_name: str, prompt: str, system_prompt: str,
                                temperature: float) -> GatewayResponse:
        start = time.time()
        if not api_key:
            return GatewayResponse(
                content="",
                provider=provider_name,
                model=model,
                latency=time.time() - start,
                success=False,
                error=f"API key missing for provider '{provider_name}'."
            )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return GatewayResponse(
                    content=content,
                    provider=provider_name,
                    model=model,
                    latency=time.time() - start,
                    success=True,
                    tokens_used=tokens
                )
        except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as e:
            return GatewayResponse(
                content="",
                provider=provider_name,
                model=model,
                latency=time.time() - start,
                success=False,
                error=f"{provider_name} request failed: {str(e)}"
            )

    def _call_anthropic(self, api_key: str, model: str, prompt: str,
                        system_prompt: str, temperature: float) -> GatewayResponse:
        """Anthropic Messages API -- system prompt alag top-level field hai."""
        start = time.time()
        if not api_key:
            return GatewayResponse(
                content="", provider="anthropic", model=model,
                latency=time.time() - start,
                success=False, error="API key missing for provider 'anthropic'."
            )
        payload = {
            "model": model,
            "max_tokens": 2048,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            req = urllib.request.Request(
                self.PROVIDER_ENDPOINTS["anthropic"],
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"
                }
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = "".join(
                    block.get("text", "") for block in data.get("content", [])
                    if isinstance(block, dict)
                )
                usage = data.get("usage", {})
                tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
                return GatewayResponse(
                    content=content, provider="anthropic", model=model,
                    latency=time.time() - start, success=True, tokens_used=tokens
                )
        except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError, IndexError) as e:
            return GatewayResponse(
                content="", provider="anthropic", model=model,
                latency=time.time() - start,
                success=False, error=f"anthropic request failed: {str(e)}"
            )

    def _call_gemini(self, api_key: str, model: str, prompt: str,
                     system_prompt: str, temperature: float) -> GatewayResponse:
        """Google Gemini generateContent API -- key query-param se jaati hai."""
        start = time.time()
        if not api_key:
            return GatewayResponse(
                content="", provider="gemini", model=model,
                latency=time.time() - start,
                success=False, error="API key missing for provider 'gemini'."
            )
        url = (
            f"{self.PROVIDER_ENDPOINTS['gemini']}/{model}:generateContent?key={api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates") or [{}]
                parts = (candidates[0].get("content") or {}).get("parts") or [{}]
                content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                tokens = int(data.get("usageMetadata", {}).get("totalTokenCount", 0))
                return GatewayResponse(
                    content=content, provider="gemini", model=model,
                    latency=time.time() - start, success=True, tokens_used=tokens
                )
        except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError, IndexError) as e:
            return GatewayResponse(
                content="", provider="gemini", model=model,
                latency=time.time() - start,
                success=False, error=f"gemini request failed: {str(e)}"
            )

    def _find_first_available_cloud_provider(self) -> Optional[str]:
        for p in ["groq", "openai", "anthropic", "gemini", "openrouter"]:
            if os.getenv(f"{p.upper()}_API_KEY"):
                return p
        return None


# Global singleton
gateway = HybridModelGateway()

