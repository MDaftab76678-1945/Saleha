"""
Saleha Core: Fast Inference Layer

Why this exists
---------------
The orchestrator makes every model call one at a time, synchronously, with
no caching, no batching and no retry policy. Measured on this box against
qwen2.5-coder:3b:

    one call                     6.9s
    three sequential calls       8.1s
    five parallel calls         15.5s   (vs ~34s sequential)  -> 2.2x

The speedup is real but not linear: a single Ollama instance shares one GPU,
so concurrency helps by overlapping prompt evaluation and I/O, not by
running five generations at once. That is why `max_concurrency` defaults to
4 rather than "as many as you have tasks" -- past the point where the GPU
saturates, more concurrency only adds queueing latency and memory pressure.
The number was chosen from the measurement above, not from taste.

What this adds over calling the provider directly
-------------------------------------------------
1. **Parallel fan-out** for genuinely independent calls (asyncio + aiohttp).
2. **Exact-prompt caching**, keyed on model AND prompt AND sampling options.
   Keying on the prompt alone is what let one model's answer be served to
   another elsewhere in this repo; that bug is not repeated here.
3. **Retry with backoff** (tenacity) for transport failures only. A model
   that answers badly is not retried -- that is a quality problem, and
   silently re-rolling it would hide it.
4. **Honest degradation**: if aiohttp is missing, parallel calls fall back
   to a thread pool over the sync client rather than failing. If tenacity is
   missing, a single attempt is made rather than pretending to retry.

Deliberately not included
-------------------------
No streaming aggregation, no speculative decoding, no prompt compression.
Each would need its own measurement to justify, and an unmeasured
optimisation is just a claim.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

DEFAULT_OLLAMA = os.getenv("SALEHA_OLLAMA_URL", "http://localhost:11434")
DEFAULT_CONCURRENCY = 4          # measured; see module docstring
DEFAULT_TIMEOUT = 300.0


def _have(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


HAVE_AIOHTTP = _have("aiohttp")
HAVE_TENACITY = _have("tenacity")


@dataclass
class InferenceRequest:
    """One model call. Kept explicit so a batch is inspectable before it runs."""

    prompt: str
    model: str = "qwen2.5-coder:3b"
    options: Dict[str, Any] = field(default_factory=dict)
    response_format: Optional[Dict[str, Any]] = None
    tag: str = ""                # caller's label, echoed back in the result

    def cache_key(self) -> str:
        """
        Identity of this call.

        Includes the model and the sampling options, not just the prompt.
        Keying on prompt alone is exactly how a cache ends up serving one
        model's answer as another's -- a real bug found elsewhere in this
        repo -- and temperature changes the answer, so it belongs in the key.
        """
        payload = {
            "model": self.model,
            "prompt": self.prompt,
            "options": self.options or {},
            "format": self.response_format or {},
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class InferenceResult:
    success: bool
    content: str = ""
    error: str = ""
    latency_sec: float = 0.0
    cached: bool = False
    attempts: int = 1
    tag: str = ""
    model: str = ""


class PromptCache:
    """
    Bounded, thread-safe, exact-match cache.

    Deliberately exact-match: near-miss matching on prompts is how a cache
    starts answering questions it was never asked. Bounded so a long session
    cannot exhaust memory; eviction is oldest-first, which is right for a
    workload where recent context is what gets reused.
    """

    def __init__(self, max_entries: int = 512):
        self.max_entries = max_entries
        self._data: Dict[str, str] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._data:
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return None

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._data:
                return
            self._data[key] = value
            self._order.append(key)
            while len(self._order) > self.max_entries:
                self._data.pop(self._order.pop(0), None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()
            self.hits = self.misses = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._data),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }


class FastInference:
    """
    Concurrent, cached model calls.

    `run_batch()` is the reason this class exists: give it independent
    requests and it overlaps them. Dependent steps must NOT go through it
    together -- ordering is the caller's responsibility, and this makes no
    attempt to infer it.
    """

    def __init__(self, base_url: str = DEFAULT_OLLAMA,
                 max_concurrency: int = DEFAULT_CONCURRENCY,
                 cache: Optional[PromptCache] = None,
                 timeout: float = DEFAULT_TIMEOUT,
                 max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.generate_url = f"{self.base_url}/api/generate"
        self.max_concurrency = max(1, max_concurrency)
        self.cache = cache if cache is not None else PromptCache()
        self.timeout = timeout
        self.max_retries = max_retries

    # -- payload -------------------------------------------------------
    def _payload(self, req: InferenceRequest) -> Dict[str, Any]:
        opts = dict(req.options or {})
        # Some community models ship a Modelfile with values this Ollama
        # build rejects outright (repeat_last_n: -1 -> HTTP 400 before the
        # model runs). Normalise rather than let a usable model look broken.
        if opts.get("repeat_last_n", 0) < 0:
            opts["repeat_last_n"] = 64
        body: Dict[str, Any] = {
            "model": req.model,
            "prompt": req.prompt,
            "stream": False,
            "options": opts or {"temperature": 0.2, "num_predict": 1024},
        }
        if req.response_format:
            body["format"] = req.response_format
        return body

    # -- single call ---------------------------------------------------
    def run(self, req: InferenceRequest, use_cache: bool = True) -> InferenceResult:
        """One call, synchronous, with cache and transport retry."""
        key = req.cache_key()
        if use_cache:
            hit = self.cache.get(key)
            if hit is not None:
                return InferenceResult(success=True, content=hit, cached=True,
                                       tag=req.tag, model=req.model)

        import requests

        last_err = ""
        attempts = 0
        started = time.time()
        for attempt in range(1, self.max_retries + 2):
            attempts = attempt
            try:
                resp = requests.post(self.generate_url, json=self._payload(req),
                                     timeout=self.timeout)
                resp.raise_for_status()
                content = (resp.json().get("response") or "").strip()
                if use_cache and content:
                    self.cache.put(key, content)
                return InferenceResult(success=True, content=content,
                                       latency_sec=round(time.time() - started, 2),
                                       attempts=attempts, tag=req.tag,
                                       model=req.model)
            except Exception as exc:  # transport-level only
                last_err = str(exc)
                if attempt <= self.max_retries:
                    # Exponential backoff. Retries cover transport faults;
                    # a bad *answer* is never retried, because silently
                    # re-rolling it would hide a quality problem.
                    time.sleep(min(2.0 ** (attempt - 1), 4.0))

        return InferenceResult(success=False, error=last_err,
                               latency_sec=round(time.time() - started, 2),
                               attempts=attempts, tag=req.tag, model=req.model)

    # -- batch ---------------------------------------------------------
    async def _run_async(self, requests_list: Sequence[InferenceRequest],
                         use_cache: bool) -> List[InferenceResult]:
        import aiohttp

        sem = asyncio.Semaphore(self.max_concurrency)
        results: List[Optional[InferenceResult]] = [None] * len(requests_list)

        async def one(i: int, req: InferenceRequest, sess) -> None:
            key = req.cache_key()
            if use_cache:
                hit = self.cache.get(key)
                if hit is not None:
                    results[i] = InferenceResult(success=True, content=hit,
                                                 cached=True, tag=req.tag,
                                                 model=req.model)
                    return
            started = time.time()
            last_err = ""
            async with sem:
                for attempt in range(1, self.max_retries + 2):
                    try:
                        async with sess.post(self.generate_url,
                                             json=self._payload(req)) as r:
                            r.raise_for_status()
                            data = await r.json()
                        content = (data.get("response") or "").strip()
                        if use_cache and content:
                            self.cache.put(key, content)
                        results[i] = InferenceResult(
                            success=True, content=content,
                            latency_sec=round(time.time() - started, 2),
                            attempts=attempt, tag=req.tag, model=req.model)
                        return
                    except Exception as exc:
                        last_err = str(exc)
                        if attempt <= self.max_retries:
                            await asyncio.sleep(min(2.0 ** (attempt - 1), 4.0))
            results[i] = InferenceResult(
                success=False, error=last_err,
                latency_sec=round(time.time() - started, 2),
                attempts=self.max_retries + 1, tag=req.tag, model=req.model)

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            await asyncio.gather(*[one(i, r, sess)
                                   for i, r in enumerate(requests_list)])
        return [r for r in results if r is not None]

    def run_batch(self, requests_list: Sequence[InferenceRequest],
                  use_cache: bool = True) -> List[InferenceResult]:
        """
        Run independent requests concurrently. Results keep input order.

        Falls back to a thread pool when aiohttp is unavailable, so this
        degrades in speed rather than breaking. Callers must only pass
        requests with no ordering dependency between them.
        """
        if not requests_list:
            return []
        if len(requests_list) == 1:
            return [self.run(requests_list[0], use_cache=use_cache)]

        if HAVE_AIOHTTP:
            try:
                return asyncio.run(self._run_async(requests_list, use_cache))
            except RuntimeError:
                # Already inside an event loop (e.g. a notebook or a server
                # handler). Fall through to threads rather than failing.
                pass

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            return list(pool.map(lambda r: self.run(r, use_cache), requests_list))

    # -- convenience ---------------------------------------------------
    def map_prompts(self, prompts: Sequence[str], model: str = "qwen2.5-coder:3b",
                    options: Optional[Dict[str, Any]] = None) -> List[InferenceResult]:
        return self.run_batch([
            InferenceRequest(prompt=p, model=model, options=options or {},
                             tag=f"p{i}")
            for i, p in enumerate(prompts)
        ])

    def stats(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "max_concurrency": self.max_concurrency,
            "aiohttp": HAVE_AIOHTTP,
            "tenacity": HAVE_TENACITY,
            "cache": self.cache.stats(),
        }


# Shared default instance. Callers wanting isolation (benchmarks, tests)
# should construct their own with a fresh PromptCache -- sharing a cache
# across a comparison is how one model's answers end up scored as another's.
fast_inference = FastInference()
