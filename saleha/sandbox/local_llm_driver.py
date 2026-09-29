import json
import urllib.request
import urllib.error
import asyncio
from typing import Dict, List, Any, Optional

class LLMUnavailableError(RuntimeError):
    """No local inference backend produced a usable answer.

    Raised instead of returning canned output: this driver used to fall back to
    a fixed "network packet parser" response (and a SHA-256-derived 16-number
    "embedding") when the daemon was down, which callers then verified, cached
    and reported as if a model had written it.
    """


class LocalLLMDriver:
    """Production driver for local inference engines (Ollama / vLLM)."""
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        vllm_url: str = "http://localhost:8000/v1",
        default_model: str = "qwen2.5-coder:7b"
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.vllm_url = vllm_url.rstrip("/")
        self.default_model = default_model

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        json_mode: bool = True,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        target_model = model or self.default_model
        failures: List[str] = []

        # 1. Try Ollama Native JSON Mode (/api/generate)
        try:
            payload = {
                "model": target_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {"temperature": temperature}
            }
            if json_mode:
                payload["format"] = "json"

            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            def _call_ollama():
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw_resp = json.loads(resp.read().decode("utf-8")).get("response", "")
                    if not raw_resp.strip():
                        raise ValueError("empty response")
                    return json.loads(raw_resp) if json_mode else {"raw_text": raw_resp}

            return await asyncio.to_thread(_call_ollama)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failures.append(f"ollama {self.ollama_url}: {exc}")

        # 2. Try vLLM / OpenAI Compatible (/v1/chat/completions)
        try:
            vllm_payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature
            }
            if json_mode:
                vllm_payload["response_format"] = {"type": "json_object"}

            req = urllib.request.Request(
                f"{self.vllm_url}/chat/completions",
                data=json.dumps(vllm_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            def _call_vllm():
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw_content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
                    return json.loads(raw_content) if json_mode else {"raw_text": raw_content}

            return await asyncio.to_thread(_call_vllm)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as exc:
            failures.append(f"vllm {self.vllm_url}: {exc}")

        raise LLMUnavailableError(
            f"No backend answered for model '{target_model}': " + "; ".join(failures)
        )

    async def get_embedding(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        payload = {"model": model, "prompt": text}
        req = urllib.request.Request(
            f"{self.ollama_url}/api/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        def _call_embed():
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, OSError, ValueError) as exc:
                raise LLMUnavailableError(f"embedding request to {self.ollama_url} failed: {exc}") from exc
            embedding = data.get("embedding", [])
            if not embedding:
                raise LLMUnavailableError(f"model '{model}' returned no embedding")
            return embedding

        return await asyncio.to_thread(_call_embed)
