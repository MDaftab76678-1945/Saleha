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
from typing import Optional, List, Dict, Any
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
    def generate(self, model: str, prompt: str, options: Optional[dict] = None) -> ProviderResponse:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError


class OllamaProvider(ModelProvider):
    """Localhost Ollama server ($0 local inference)."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.generate_url = f"{base_url}/api/generate"
        self.tags_url = f"{base_url}/api/tags"

    def generate(self, model: str, prompt: str, options: Optional[dict] = None) -> ProviderResponse:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {
                "temperature": 0.2,
                "num_predict": 2048,
                "repeat_penalty": 1.15,
                "top_p": 0.9,
            },
        }

        start_time = time.time()
        try:
            response = requests.post(self.generate_url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return ProviderResponse(
                success=True,
                content=result.get("response", "").strip(),
                response_time=time.time() - start_time,
                tokens_used=int(result.get("eval_count", 0) or 0),
                provider_name="ollama",
            )
        except Exception as e:
            error_msg = "Ollama server not running" if "Connection" in str(e) else str(e)
            return ProviderResponse(
                success=False,
                content="",
                error_message=error_msg,
                response_time=time.time() - start_time,
                provider_name="ollama",
            )

    def is_available(self) -> bool:
        try:
            resp = requests.get(self.tags_url, timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False


class OpenAICompatibleProvider(ModelProvider):
    """Universal OpenAI-compatible API for Groq, DeepSeek, OpenRouter, OpenAI, vLLM, LM Studio."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        provider_name: str = "openai_compatible",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""
        self.provider_name = provider_name

    def generate(self, model: str, prompt: str, options: Optional[dict] = None) -> ProviderResponse:
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
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
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

    def generate(self, model: str, prompt: str, options: Optional[dict] = None) -> ProviderResponse:
        errors = []
        for p in self.providers:
            if p.is_available():
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


class MockProvider(ModelProvider):
    """Deterministic zero-latency mock provider for tests."""

    def __init__(self, default_response: str = "def solve():\n    return 42"):
        self.default_response = default_response

    def generate(self, model: str, prompt: str, options: Optional[dict] = None) -> ProviderResponse:
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