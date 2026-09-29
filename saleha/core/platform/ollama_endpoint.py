"""
Where to reach Ollama, from `SALEHA_OLLAMA_URL` / `OLLAMA_HOST`.

`OLLAMA_HOST` is the *server's* bind setting, and on this machine it is
`0.0.0.0:11434`: scheme-less, which urllib cannot open, and a bind address,
not a client address. Every client has to normalise it. There were two
copies of that normalisation (`rag.embedding_backends`, `real_task_bench`) and
a third client (`sandbox.local_llm_driver`) that ignored the variable and
hard-coded localhost. They all use this module now.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
_DEFAULT_PORT = 11434
# Addresses a server binds to but a client cannot usefully connect to, plus
# `localhost`, which can cost a slow IPv6 lookup first on Windows.
_LOOPBACK_ALIASES = {"0.0.0.0", "::", "localhost", ""}


def normalize_ollama_url(raw: Optional[str]) -> str:
    """Turn any OLLAMA_HOST-style value into a client base URL (no trailing slash)."""
    text = (raw or "").strip()
    if not text:
        return DEFAULT_OLLAMA_URL
    if "://" not in text:
        text = f"http://{text}"
    parts = urlsplit(text)
    host = parts.hostname or ""
    try:
        port = parts.port or _DEFAULT_PORT
    except ValueError:  # non-numeric port: leave it for the connection to reject
        return text.rstrip("/")
    if host in _LOOPBACK_ALIASES:
        host = "127.0.0.1"
    netloc = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    return urlunsplit((parts.scheme or "http", netloc, parts.path.rstrip("/"), "", ""))


def ollama_base_url() -> str:
    """The Ollama base URL for this process: SALEHA_OLLAMA_URL, else OLLAMA_HOST, else the default."""
    return normalize_ollama_url(os.environ.get("SALEHA_OLLAMA_URL") or os.environ.get("OLLAMA_HOST"))
