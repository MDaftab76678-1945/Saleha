import json
import urllib.request
import urllib.error
import asyncio
from typing import Dict, List, Any, Optional

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
                    raw_resp = json.loads(resp.read().decode("utf-8")).get("response", "{}")
                    return json.loads(raw_resp) if json_mode else {"raw_text": raw_resp}

            return await asyncio.to_thread(_call_ollama)
        except urllib.error.URLError:
            pass

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
        except Exception as e:
            # No model answered. This used to return a canned "parse_payload"
            # script whose own self-test printed SELF_TEST_PASSED, so the
            # healing loop "passed" tasks it never sent to a model. Say so.
            return {"error": (f"no local model reachable at {self.ollama_url} or "
                              f"{self.vllm_url}: {type(e).__name__}: {e}")}

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
                    return data.get("embedding", [])
            except Exception:
                # Empty, not a hash of the text: a fake vector would rank
                # "similar" documents by byte noise and look like it worked.
                return []

        return await asyncio.to_thread(_call_embed)
