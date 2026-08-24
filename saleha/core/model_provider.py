"""
Saleha Core: Model Provider Abstraction (New)

Abhi base_agent.py seedha Ollama ke HTTP API (localhost:11434) se hardcoded
connect hai. Agar kabhi:
  - Ollama ke bajaye koi doosra local server use karna ho (jaise llama.cpp
    server, LM Studio, vLLM)
  - Kisi cloud API pe fallback chahiye ho jab local model available na ho
  - Testing ke liye ek fake/mock provider chahiye ho

...to abhi `base_agent.py` ke andar HTTP call directly likhi hai, jise
badalna matlab base_agent.py khud chhedna. Ye abstraction isse alag karta
hai: koi bhi ModelProvider is interface ko implement kare, base_agent.py
sirf `provider.generate(...)` bulata hai, kaunsa backend hai use farq nahi
padta.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import requests
import json
import time
import urllib.error


@dataclass
class ProviderResponse:
    success: bool
    content: str
    error_message: str = ""
    response_time: float = 0.0
    tokens_used: int = 0


class ModelProvider(ABC):
    """Har naya backend (Ollama, llama.cpp, cloud API) isse inherit karega."""

    @abstractmethod
    def generate(self, model: str, prompt: str, options: Optional[dict] = None) -> ProviderResponse:
        """Model se ek response generate karwao. `options` provider-specific
        settings hai (temperature, num_predict, etc.) -- caller isse pass
        karta hai, provider apne format me convert karta hai."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Ye provider abhi reachable/usable hai? (health check)"""
        raise NotImplementedError


class OllamaProvider(ModelProvider):
    """Abhi Saleha jo use karta hai -- localhost Ollama server."""

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
                "temperature": 0.3,
                "num_predict": 1500,
                "repeat_penalty": 1.2,
                "top_k": 40,
                "top_p": 0.9,
            },
        }

        start_time = time.time()
        try:
            response = requests.post(self.generate_url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return ProviderResponse(
                success=True,
                content=result.get("response", "").strip(),
                response_time=time.time() - start_time,
                tokens_used=int(result.get("eval_count", 0) or 0),
            )
        except Exception as e:
            error_msg = "Ollama server not running" if "Connection" in str(e) else str(e)
            return ProviderResponse(
                success=False,
                content="",
                error_message=error_msg,
                response_time=time.time() - start_time,
            )

    def stream_generate(self, model: str, prompt: str, callback=None, options: Optional[dict] = None) -> ProviderResponse:
        """Streams generated tokens in real-time via Ollama chunk streaming."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": options or {
                "temperature": 0.3,
                "num_predict": 1500,
                "repeat_penalty": 1.2,
                "top_k": 40,
                "top_p": 0.9,
            },
        }

        start_time = time.time()
        accumulated = []
        tokens_used = 0
        try:
            with requests.post(self.generate_url, json=payload, stream=True, timeout=120) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            accumulated.append(token)
                            if callback and token:
                                callback(token)
                            if chunk.get("done", False):
                                tokens_used = int(chunk.get("eval_count", 0) or 0)
                                break
                        except Exception:
                            continue

            full_content = "".join(accumulated).strip()
            return ProviderResponse(
                success=True,
                content=full_content,
                response_time=time.time() - start_time,
                tokens_used=tokens_used,
            )
        except Exception as e:
            error_msg = "Ollama server not running" if "Connection" in str(e) else str(e)
            return ProviderResponse(
                success=False,
                content="".join(accumulated),
                error_message=error_msg,
                response_time=time.time() - start_time,
                tokens_used=tokens_used,
            )

    def is_available(self) -> bool:
        try:
            resp = requests.get(self.tags_url, timeout=3)
            return resp.status_code == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False


# Default provider -- baaki poora Saleha ismse hi baat karta hai.
# Kabhi provider badalna ho (jaise config se), sirf yahan badlo.
default_provider: ModelProvider = OllamaProvider()


if __name__ == "__main__":
    print("Model Provider Test")
    provider = default_provider
    print(f"Provider available: {provider.is_available()}")

    if provider.is_available():
        result = provider.generate(model="qwen3.5:0.8b", prompt="Say hello in one word.")
        print(f"Success: {result.success}")
        print(f"Content: {result.content}")
        print(f"Time: {result.response_time:.2f}s")
    else:
        print("Ollama not reachable -- skipping generate test.")