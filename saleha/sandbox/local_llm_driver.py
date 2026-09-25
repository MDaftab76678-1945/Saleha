"""
Driver for local inference engines: Ollama first, then a vLLM /
OpenAI-compatible server.

Every failure comes back as `{"error": ...}` -- a backend that is down, a
model that is not installed, output that is not the JSON that was asked for.
It used to catch only `URLError` from Ollama, so:

- model output that was not JSON raised `JSONDecodeError` out of
  `generate_structured` instead of reporting it;
- a read timeout (`TimeoutError`) escaped the same way;
- an Ollama reply with no `response` field became `{}`, an empty result that
  reads as success;
- an Ollama 404 ("model not found") fell through to vLLM and was reported as a
  vLLM connection error, hiding the real cause.

It also ignored `OLLAMA_HOST` and defaulted to `qwen2.5-coder:7b`, which is not
installed here. The host now comes from `saleha.core.ollama_endpoint`.
"""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from saleha.core.ollama_endpoint import normalize_ollama_url, ollama_base_url

DEFAULT_MODEL = "qwen2.5-coder:3b"


def _describe_http_failure(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        return f"HTTP {exc.code}: {body[:200] or exc.reason}"
    return f"{type(exc).__name__}: {exc}"


def _shape_output(text: Any, json_mode: bool, source: str) -> Dict[str, Any]:
    """Turn a model's text into the result dict, or an error saying why it cannot be."""
    if not isinstance(text, str):
        return {"error": f"{source} reply had no text output (got {type(text).__name__})"}
    if not json_mode:
        return {"raw_text": text}
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"error": f"{source} model output was not valid JSON: {text[:200]!r}"}
    if not isinstance(parsed, dict):
        return {"error": f"{source} model output was JSON {type(parsed).__name__}, not an object"}
    return parsed


class LocalLLMDriver:
    """Production driver for local inference engines (Ollama / vLLM)."""

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        vllm_url: str = "http://127.0.0.1:8000/v1",
        default_model: str = DEFAULT_MODEL,
    ):
        self.ollama_url = normalize_ollama_url(ollama_url) if ollama_url else ollama_base_url()
        self.vllm_url = vllm_url.rstrip("/")
        self.default_model = default_model

    @staticmethod
    def _post_json(url: str, payload: Dict[str, Any], timeout: int) -> Any:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        json_mode: bool = True,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Returns the parsed JSON object (json_mode) or `{"raw_text": ...}`,
        or `{"error": ...}` naming every backend tried and why each failed.

        A backend that answered is final: its output is shaped and returned
        even when it is unusable. Only a backend that could not be reached or
        returned an HTTP/transport error hands over to the next one.
        """
        target_model = model or self.default_model
        failures: List[str] = []

        # 1. Ollama native API (/api/generate)
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            body = await asyncio.to_thread(self._post_json, f"{self.ollama_url}/api/generate", payload, 90)
        except Exception as e:
            failures.append(f"ollama at {self.ollama_url}: {_describe_http_failure(e)}")
        else:
            text = body.get("response") if isinstance(body, dict) else None
            return _shape_output(text, json_mode, "ollama")

        # 2. vLLM / OpenAI-compatible (/v1/chat/completions)
        vllm_payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        if json_mode:
            vllm_payload["response_format"] = {"type": "json_object"}
        try:
            body = await asyncio.to_thread(self._post_json, f"{self.vllm_url}/chat/completions", vllm_payload, 90)
        except Exception as e:
            failures.append(f"vllm at {self.vllm_url}: {_describe_http_failure(e)}")
        else:
            try:
                text = body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                return {"error": f"vllm reply had an unexpected shape: {str(body)[:200]}"}
            return _shape_output(text, json_mode, "vllm")

        # No model answered. This used to return a canned "parse_payload"
        # script whose own self-test printed SELF_TEST_PASSED, so the healing
        # loop "passed" tasks it never sent to a model.
        return {"error": "no local model answered -- " + "; ".join(failures)}

    async def get_embedding(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        payload = {"model": model, "prompt": text}

        def _call_embed() -> List[float]:
            try:
                data = self._post_json(f"{self.ollama_url}/api/embeddings", payload, 30)
            except Exception:
                # Empty, not a hash of the text: a fake vector would rank
                # "similar" documents by byte noise and look like it worked.
                return []
            vec = data.get("embedding") if isinstance(data, dict) else None
            return vec if isinstance(vec, list) else []

        return await asyncio.to_thread(_call_embed)
