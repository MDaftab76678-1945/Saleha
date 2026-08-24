"""
Saleha Core: Vision Backend (Real Multimodal -- stub se upgrade)

Pehle `vision_coder` sirf text-spec se template/LLM generate karta tha --
IMAGE kabhi dekhi hi nahi jaati thi (web endpoint me hardcoded dry_run).
Ab local Ollama ke vision models (llava, qwen2-vl, llama3.2-vision,
minicpm-v, moondream...) se SCREENSHOT -> working UI code hota hai:

    POST /api/generate {"model": "llava:13b", "images": ["<base64>"], ...}

Graceful degradation built-in: vision model installed na ho ya call fail ho
to text-only pipeline / template pe fall back (used_vision=False flag se
caller ko pata rehta hai kya hua).
"""

import base64
import os
import re
import time
from typing import List, Optional, Tuple

import requests

# Known Ollama vision-capable model families (2026 catalog)
_VISION_MODEL_PATTERNS = (
    "llava", "bakllava", "moondream", "minicpm-v", "llama3.2-vision",
    "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "gemma3",
)

_CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z]+)?\s*(.*?)```", re.DOTALL)


def find_vision_model() -> Optional[str]:
    """Installed Ollama models me pehla vision-capable model return karta hai.

    Reuses SmartRouter ka runtime probe (~/.saleha consistency). None =
    koi vision model nahi mila (caller ko fallback chalana chahiye).
    """
    from saleha.core.smart_router import get_installed_ollama_models
    installed = get_installed_ollama_models()
    for model in sorted(installed):
        lowered = model.lower()
        if any(pat in lowered for pat in _VISION_MODEL_PATTERNS):
            return model
    return None


def load_image_b64(source: str) -> Tuple[str, str]:
    """Image source (file path YA base64/data-URL) -> (raw_b64, media_note).

    Raises ValueError invalid input par.
    """
    if not source or not source.strip():
        raise ValueError("empty image source")
    source = source.strip()
    if source.startswith("data:image"):
        # data URL: "data:image/png;base64,<b64>"
        _, _, b64part = source.partition(",")
        b64 = b64part.strip()
        if not b64:
            raise ValueError("data URL with empty payload")
        return b64, "data-url"
    if os.path.isfile(source):
        try:
            with open(source, "rb") as f:
                raw = f.read()
        except OSError as err:
            raise ValueError(f"cannot read image file: {err}")
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("image too large (>8MB)")
        if not raw[:8] in (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1") and not raw[:3] == b"GIF":
            # Unknown magic -- phir bhi allow (Ollama khud validate karega)
            pass
        return base64.b64encode(raw).decode("ascii"), f"file:{os.path.basename(source)} ({len(raw)} bytes)"
    # Raw base64 string maan lo
    try:
        base64.b64decode(source[:64], validate=True)
    except Exception:
        raise ValueError("image source is neither a valid file path nor base64")
    return source, "raw-base64"


def generate_code_from_image(image_b64: str, layout_spec: str,
                             system_prompt: str,
                             model: Optional[str] = None,
                             timeout: int = 180) -> Tuple[Optional[str], str]:
    """Vision model se UI code generate karta hai.

    Returns:
        (code_or_None, model_used) -- code None => failure (caller fallback).
    """
    chosen = model or find_vision_model()
    if not chosen:
        return None, ""
    base_url = os.getenv("SALEHA_OLLAMA_URL", "http://localhost:11434")
    payload = {
        "model": chosen,
        "prompt": (
            f"{system_prompt}\n\n"
            f"Analyze the attached screenshot/wireframe carefully.\n"
            f"Extra requirements from developer: {layout_spec or '(none)'}\n"
            f"Reproduce this UI as complete, production-grade code."
        ),
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 2500},
    }
    try:
        resp = requests.post(f"{base_url}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
        content = resp.json().get("response", "").strip()
    except (requests.RequestException, ValueError):
        return None, chosen
    if not content:
        return None, chosen
    fence = _CODE_FENCE_RE.search(content)
    code = fence.group(1).strip() if fence else content
    return code, chosen
