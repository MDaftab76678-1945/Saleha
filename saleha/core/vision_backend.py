"""
Saleha Core: Vision Backend (Multimodal UI Generation)

Provides local Ollama vision model integration (llava, qwen2-vl, llama3.2-vision,
minicpm-v, moondream...) to transform screenshots and wireframes into working UI code:

    POST /api/generate {"model": "llava:13b", "images": ["<base64>"], ...}

Graceful degradation built-in: if no vision model is installed or the call fails,
the pipeline falls back to text-only template generation with `used_vision=False`.
"""

from __future__ import annotations

import base64
import os
import re
from typing import Optional, Tuple

import requests

# Known Ollama vision-capable model families (2026 catalog)
_VISION_MODEL_PATTERNS = (
    "llava", "bakllava", "moondream", "minicpm-v", "llama3.2-vision",
    "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "gemma3",
)

_CODE_FENCE_RE = re.compile(r"```(?:[a-zA-Z]+)?\s*(.*?)```", re.DOTALL)


def find_vision_model() -> Optional[str]:
    """Returns the first vision-capable model found among installed Ollama models.

    Uses SmartRouter runtime probe (~/.saleha consistency). Returns None if
    no vision model is found (signaling the caller to use fallback).
    """
    from saleha.core.smart_router import get_installed_ollama_models
    installed = get_installed_ollama_models()
    for model in sorted(installed):
        lowered = model.lower()
        if any(pat in lowered for pat in _VISION_MODEL_PATTERNS):
            return model
    return None


def load_image_b64(source: str) -> Tuple[str, str]:
    """Converts image source (file path or base64/data-URL) to (raw_b64, media_note).

    Raises ValueError on invalid input.
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
            raise ValueError(f"cannot read image file: {err}") from err
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("image too large (>8MB)")
        if raw[:8] not in (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1") and raw[:3] != b"GIF":
            # Unknown magic -- still allow through for Ollama's own validation
            pass
        return base64.b64encode(raw).decode("ascii"), f"file:{os.path.basename(source)} ({len(raw)} bytes)"
    # Fallback to raw base64 string
    try:
        base64.b64decode(source[:64], validate=True)
    except Exception:
        raise ValueError("image source is neither a valid file path nor base64") from None
    return source, "raw-base64"


def generate_code_from_image(image_b64: str, layout_spec: str,
                             system_prompt: str,
                             model: Optional[str] = None,
                             timeout: int = 180) -> Tuple[Optional[str], str]:
    """Generates UI component code from an image input using an Ollama vision model.

    Returns:
        (code_or_None, model_used) -- code is None on failure (triggering fallback).
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
