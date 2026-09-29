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
3. **Retry with jittered backoff** for transient failures only: a refused
   or reset connection, HTTP 408/429/502/503/504. A timed-out generation is
   not retried (it used to be, twice: one hung model cost three full
   timeouts per request), nor is a 4xx, nor a model that answers badly --
   that is a quality problem, and silently re-rolling it would hide it.
4. **Circuit breaker** shared with OllamaProvider (platform/circuit_breaker):
   after consecutive failures, calls answer "not sent" at once instead of
   paying the failure again.
5. **Honest degradation**: if aiohttp is missing, or an event loop is
   already running, parallel calls fall back to a thread pool over the sync
   client rather than failing.

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
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from saleha.core.ollama_endpoint import ollama_base_url
from saleha.core.platform.async_ollama import (
    Exchange,
    GenerateRequest,
    ResultKind,
    interpret_answer,
)
from saleha.core.platform.circuit_breaker import (
    AttemptOutcome,
    CircuitBreaker,
    Health,
    RetryPolicy,
    next_delay,
    parse_retry_after,
    shared_breaker,
)

DEFAULT_CONCURRENCY = 4          # measured; see module docstring
DEFAULT_TIMEOUT = 300.0
CONNECT_TIMEOUT = 5.0


def _have(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


HAVE_AIOHTTP = _have("aiohttp")


def _event_loop_running() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


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

    def __init__(self, base_url: Optional[str] = None,
                 max_concurrency: int = DEFAULT_CONCURRENCY,
                 cache: Optional[PromptCache] = None,
                 timeout: float = DEFAULT_TIMEOUT,
                 max_retries: int = 2,
                 breaker: Optional[CircuitBreaker] = None):
        self.base_url = (base_url or ollama_base_url()).rstrip("/")
        self.generate_url = f"{self.base_url}/api/generate"
        self.max_concurrency = max(1, max_concurrency)
        self.cache = cache if cache is not None else PromptCache()
        # Per request, retries included: a retry never starts a sleep that
        # would end past it.
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry = RetryPolicy(max_attempts=max_retries + 1)
        self.breaker = breaker or shared_breaker()
        self._rng = random.Random()

    # -- payload -------------------------------------------------------
    def _request(self, req: InferenceRequest) -> GenerateRequest:
        opts = dict(req.options or {})
        # Some community models ship a Modelfile with values this Ollama
        # build rejects outright (repeat_last_n: -1 -> HTTP 400 before the
        # model runs). Normalise rather than let a usable model look broken.
        if opts.get("repeat_last_n", 0) < 0:
            opts["repeat_last_n"] = 64
        return GenerateRequest(model=req.model, prompt=req.prompt,
                               options=opts or {"temperature": 0.2, "num_predict": 1024},
                               response_format=req.response_format or None)

    def _payload(self, req: InferenceRequest) -> Dict[str, Any]:
        return self._request(req).payload()

    # -- single call ---------------------------------------------------
    def run(self, req: InferenceRequest, use_cache: bool = True) -> InferenceResult:
        """One call, synchronous, with cache, circuit breaker and transient-failure retry."""
        key = req.cache_key()
        if use_cache:
            hit = self.cache.get(key)
            if hit is not None:
                return InferenceResult(success=True, content=hit, cached=True,
                                       tag=req.tag, model=req.model)

        started = time.monotonic()
        deadline = started + self.timeout
        body = self._payload(req)
        attempts = 0
        while True:
            admission = self.breaker.admit(self.base_url)
            if not admission.allowed:
                return InferenceResult(success=False, error=f"not sent: {admission.reason}",
                                       latency_sec=round(time.monotonic() - started, 2),
                                       attempts=attempts, tag=req.tag, model=req.model)
            attempts += 1
            try:
                ex = self._post_once(body, max(0.001, deadline - time.monotonic()))
            except BaseException:
                self.breaker.record(self.base_url, admission, Health.UNKNOWN, "call did not finish")
                raise
            self.breaker.record(self.base_url, admission, ex.outcome.health, ex.error)
            delay = next_delay(self.retry, attempts, ex.outcome, deadline - time.monotonic(), self._rng)
            if delay is None:
                if ex.kind is ResultKind.OK and use_cache:
                    self.cache.put(key, ex.text)
                return InferenceResult(success=ex.kind is ResultKind.OK, content=ex.text,
                                       error=ex.error,
                                       latency_sec=round(time.monotonic() - started, 2),
                                       attempts=attempts, tag=req.tag, model=req.model)
            time.sleep(delay)

    def _post_once(self, body: Dict[str, Any], read_timeout: float) -> Exchange:
        import requests

        try:
            resp = requests.post(self.generate_url, json=body,
                                 timeout=(CONNECT_TIMEOUT, read_timeout))
        except requests.exceptions.ConnectTimeout:
            return Exchange(ResultKind.UNREACHABLE, AttemptOutcome(Health.UNHEALTHY, retryable=True),
                            f"no connection to {self.base_url} within {CONNECT_TIMEOUT:g}s")
        except requests.exceptions.Timeout:
            return Exchange(ResultKind.TIMEOUT, AttemptOutcome(Health.UNHEALTHY, retryable=False),
                            f"no complete answer within {read_timeout:g}s")
        except requests.exceptions.ConnectionError as exc:
            return Exchange(ResultKind.UNREACHABLE, AttemptOutcome(Health.UNHEALTHY, retryable=True),
                            f"cannot connect to {self.base_url}: {exc}")
        except requests.exceptions.RequestException as exc:  # bad URL or similar: not the server
            return Exchange(ResultKind.UNREACHABLE, AttemptOutcome(Health.UNKNOWN, retryable=False),
                            f"request failed: {type(exc).__name__}: {exc}")
        except OSError as exc:
            return Exchange(ResultKind.UNREACHABLE, AttemptOutcome(Health.UNHEALTHY, retryable=True),
                            f"{type(exc).__name__}: {exc}")
        return interpret_answer(resp.status_code, resp.content,
                                parse_retry_after(resp.headers.get("Retry-After")))

    # -- batch ---------------------------------------------------------
    async def _run_async(self, requests_list: Sequence[InferenceRequest],
                         use_cache: bool) -> List[InferenceResult]:
        from saleha.core.platform.async_ollama import AsyncOllamaClient, ClientConfig

        results: List[Optional[InferenceResult]] = [None] * len(requests_list)
        pending: List[Tuple[int, InferenceRequest]] = []
        for i, req in enumerate(requests_list):
            hit = self.cache.get(req.cache_key()) if use_cache else None
            if hit is not None:
                results[i] = InferenceResult(success=True, content=hit, cached=True,
                                             tag=req.tag, model=req.model)
            else:
                pending.append((i, req))

        config = ClientConfig(base_url=self.base_url, max_in_flight=self.max_concurrency,
                              connect_timeout=CONNECT_TIMEOUT, read_timeout=self.timeout,
                              total_timeout=self.timeout, retry=self.retry)
        async with AsyncOllamaClient(config, breaker=self.breaker, rng=self._rng) as client:
            answers = await client.generate_many([self._request(req) for _, req in pending])
        for (i, req), answer in zip(pending, answers, strict=True):
            if answer.ok and use_cache:
                self.cache.put(req.cache_key(), answer.text)
            results[i] = InferenceResult(success=answer.ok, content=answer.text, error=answer.error,
                                         latency_sec=round(answer.seconds, 2),
                                         attempts=answer.attempts, tag=req.tag, model=req.model)
        return cast(List[InferenceResult], results)  # every index was filled above

    def run_batch(self, requests_list: Sequence[InferenceRequest],
                  use_cache: bool = True) -> List[InferenceResult]:
        """
        Run independent requests concurrently. Results keep input order.

        Falls back to a thread pool when aiohttp is unavailable or an event
        loop is already running here, so this degrades in speed rather than
        breaking. Callers must only pass requests with no ordering
        dependency between them.
        """
        if not requests_list:
            return []
        if len(requests_list) == 1:
            return [self.run(requests_list[0], use_cache=use_cache)]

        # Checked up front: catching asyncio.run's RuntimeError also caught
        # any RuntimeError raised inside the batch and silently re-sent every
        # request on threads.
        if HAVE_AIOHTTP and not _event_loop_running():
            return asyncio.run(self._run_async(requests_list, use_cache))

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
            "cache": self.cache.stats(),
        }


# Shared default instance. Callers wanting isolation (benchmarks, tests)
# should construct their own with a fresh PromptCache -- sharing a cache
# across a comparison is how one model's answers end up scored as another's.
fast_inference = FastInference()
