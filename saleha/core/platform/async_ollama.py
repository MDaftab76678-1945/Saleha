"""
Async Ollama client for fan-out: one pooled set of connections, a bulkhead on
in-flight generations, an explicit timeout on every phase, jittered retries
for transient failures only, and the process-wide circuit breaker.

Every phase has its own limit (`ClientConfig`):
  queue_timeout    waiting for an in-flight slot. Local; never blamed on the server.
  connect_timeout  opening a TCP connection.
  read_timeout     one attempt, from sending to the last byte of the answer.
  total_timeout    everything after the slot is taken: attempts plus backoff sleeps.

Retried: refused or reset connections, connect timeouts, HTTP 408/429/502/503/504.
Not retried: a read timeout (the model just spent read_timeout on this
prompt; asking again doubles the wait), other 4xx (the request is wrong),
other 5xx (usually this input), an empty or malformed answer.

The connection pool is sized to `max_in_flight`, the same bound the bulkhead
enforces, so a request never waits for a pooled connection and a connect
timeout always means the server, not a busy pool.

Results are typed (`ResultKind`) so "not sent" (circuit open, no free slot)
never reads like a model failure, and neither reads like success.
"""

from __future__ import annotations

import asyncio
import enum
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence, cast

from saleha.core.platform.circuit_breaker import (
    AttemptOutcome,
    CircuitBreaker,
    Health,
    RetryPolicy,
    classify_status,
    next_delay,
    parse_retry_after,
    shared_breaker,
)
from saleha.core.platform.ollama_endpoint import ollama_base_url

if TYPE_CHECKING:
    import aiohttp

logger = logging.getLogger(__name__)

_CHUNK = 64 * 1024


class ResultKind(enum.Enum):
    OK = "ok"
    EMPTY = "empty"  # HTTP 200, but the model generated nothing
    REJECTED = "rejected"  # 4xx: this request was refused (unknown model, bad option)
    BUSY = "busy"  # 429/503 on the last attempt
    SERVER_ERROR = "server_error"  # other 5xx, a dropped connection, a malformed or oversized answer
    TIMEOUT = "timeout"  # no complete answer within read_timeout / total_timeout
    UNREACHABLE = "unreachable"  # could not connect
    CIRCUIT_OPEN = "circuit_open"  # not sent: the server failed recently
    QUEUE_TIMEOUT = "queue_timeout"  # not sent: no free slot within queue_timeout


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    prompt: str
    options: Mapping[str, Any] = field(default_factory=dict)
    response_format: Any = None  # Ollama `format`: "json" or a JSON schema
    think: Optional[bool] = None

    def payload(self) -> Dict[str, Any]:
        body: Dict[str, Any] = {"model": self.model, "prompt": self.prompt, "stream": False,
                                "options": dict(self.options)}
        if self.response_format is not None:
            body["format"] = self.response_format
        if self.think is not None:
            body["think"] = self.think
        return body


@dataclass(frozen=True)
class GenerateResult:
    kind: ResultKind
    text: str = ""
    error: str = ""
    attempts: int = 0  # requests actually sent
    seconds: float = 0.0
    status: Optional[int] = None
    eval_count: int = 0
    done_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.kind is ResultKind.OK


@dataclass(frozen=True)
class ClientConfig:
    base_url: str = field(default_factory=ollama_base_url)
    max_in_flight: int = 4
    connect_timeout: float = 5.0
    read_timeout: float = 300.0
    total_timeout: float = 360.0
    queue_timeout: float = 3600.0
    keepalive_seconds: float = 30.0
    max_body_bytes: int = 32 * 1024 * 1024
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"base_url must start with http:// or https://, got {self.base_url!r}")
        if self.max_in_flight < 1:
            raise ValueError(f"max_in_flight must be >= 1, got {self.max_in_flight}")
        for name in ("connect_timeout", "read_timeout", "total_timeout", "queue_timeout", "keepalive_seconds"):
            value = getattr(self, name)
            if not (value > 0 and math.isfinite(value)):
                raise ValueError(f"{name} must be a positive number, got {value}")
        if self.max_body_bytes < 1:
            raise ValueError(f"max_body_bytes must be >= 1, got {self.max_body_bytes}")

    @property
    def breaker_key(self) -> str:
        return self.base_url.rstrip("/")

    @property
    def generate_url(self) -> str:
        return self.breaker_key + "/api/generate"


@dataclass(frozen=True)
class Exchange:
    """One attempt, before retry and breaker bookkeeping. The sync path in fast_inference builds these too."""

    kind: ResultKind
    outcome: AttemptOutcome
    error: str = ""
    text: str = ""
    status: Optional[int] = None
    eval_count: int = 0
    done_reason: str = ""


class _BodyTooLarge(Exception):
    pass


class AsyncOllamaClient:
    """
    `async with AsyncOllamaClient(config) as client:` owns one connection
    pool for its lifetime. Request state lives in local variables and the
    breaker's store, never on the client.
    """

    def __init__(self, config: Optional[ClientConfig] = None, *, breaker: Optional[CircuitBreaker] = None,
                 rng: Optional[random.Random] = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config or ClientConfig()
        self.breaker = breaker or shared_breaker()
        self._rng = rng or random.Random()
        self._clock = clock
        self._session: Optional[aiohttp.ClientSession] = None
        self._slots: Optional[asyncio.Semaphore] = None

    async def __aenter__(self) -> AsyncOllamaClient:
        import aiohttp

        if self._session is not None:
            raise RuntimeError("AsyncOllamaClient is already open")
        cfg = self.config
        connector = aiohttp.TCPConnector(limit=cfg.max_in_flight, limit_per_host=cfg.max_in_flight,
                                         keepalive_timeout=cfg.keepalive_seconds)
        self._session = aiohttp.ClientSession(connector=connector)
        self._slots = asyncio.Semaphore(cfg.max_in_flight)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        session, self._session, self._slots = self._session, None, None
        if session is not None:
            await session.close()

    async def generate_many(self, requests: Sequence[GenerateRequest]) -> List[GenerateResult]:
        """Run independent requests with at most `max_in_flight` workers. Results keep input order."""
        results: List[Optional[GenerateResult]] = [None] * len(requests)
        work = iter(enumerate(requests))  # shared by the workers; one event loop, so no lock

        async def worker() -> None:
            for index, request in work:
                results[index] = await self.generate(request)

        async with asyncio.TaskGroup() as group:
            for _ in range(min(self.config.max_in_flight, len(requests))):
                group.create_task(worker())
        return cast(List[GenerateResult], results)  # every slot is filled once the group exits cleanly

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        session, slots = self._session, self._slots
        if session is None or slots is None:
            raise RuntimeError("AsyncOllamaClient is not open; use 'async with AsyncOllamaClient(...)'")
        started = self._clock()
        try:
            async with asyncio.timeout(self.config.queue_timeout):
                await slots.acquire()
        except TimeoutError:
            return GenerateResult(ResultKind.QUEUE_TIMEOUT, seconds=self._clock() - started,
                                  error=f"not sent: no free slot within {self.config.queue_timeout:g}s")
        try:
            return await self._attempts(session, request, started)
        finally:
            slots.release()

    async def _attempts(self, session: aiohttp.ClientSession, request: GenerateRequest,
                        started: float) -> GenerateResult:
        cfg = self.config
        key = cfg.breaker_key
        body = request.payload()
        deadline = self._clock() + cfg.total_timeout
        attempts = 0
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return GenerateResult(ResultKind.TIMEOUT, attempts=attempts, seconds=self._clock() - started,
                                      error=f"total_timeout of {cfg.total_timeout:g}s spent "
                                            f"after {attempts} attempt(s)")
            admission = self.breaker.admit(key)
            if not admission.allowed:
                wait = f"; next try in {admission.retry_after:.0f}s" if admission.retry_after else ""
                return GenerateResult(ResultKind.CIRCUIT_OPEN, attempts=attempts,
                                      seconds=self._clock() - started,
                                      error=f"not sent: {admission.reason}{wait}")
            attempts += 1
            try:
                ex = await self._send_once(session, body, min(cfg.read_timeout, remaining))
            except BaseException:
                # Cancelled (or a bug): the server was not judged, and a probe slot must come back.
                self.breaker.record(key, admission, Health.UNKNOWN, "call did not finish")
                raise
            self.breaker.record(key, admission, ex.outcome.health, ex.error)
            delay = next_delay(cfg.retry, attempts, ex.outcome, deadline - self._clock(), self._rng)
            if delay is None:
                return GenerateResult(ex.kind, text=ex.text, error=ex.error, attempts=attempts,
                                      seconds=self._clock() - started, status=ex.status,
                                      eval_count=ex.eval_count, done_reason=ex.done_reason)
            logger.info("%s attempt %d: %s; retrying in %.2fs", key, attempts, ex.error, delay)
            await asyncio.sleep(delay)

    async def _send_once(self, session: aiohttp.ClientSession, body: Dict[str, Any],
                         timeout: float) -> Exchange:
        import aiohttp

        cfg = self.config
        limits = aiohttp.ClientTimeout(total=timeout, connect=cfg.connect_timeout,
                                       sock_connect=cfg.connect_timeout)
        try:
            async with session.post(cfg.generate_url, json=body, timeout=limits) as resp:
                status = resp.status
                retry_after = parse_retry_after(resp.headers.get("Retry-After"))
                raw = await _read_capped(resp.content, cfg.max_body_bytes)
        except aiohttp.ConnectionTimeoutError:
            return Exchange(ResultKind.UNREACHABLE, AttemptOutcome(Health.UNHEALTHY, retryable=True),
                             f"no connection to {cfg.base_url} within {cfg.connect_timeout:g}s")
        except aiohttp.ClientConnectorError as exc:
            return Exchange(ResultKind.UNREACHABLE, AttemptOutcome(Health.UNHEALTHY, retryable=True),
                             f"cannot connect to {cfg.base_url}: {exc}")
        except TimeoutError:
            return Exchange(ResultKind.TIMEOUT, AttemptOutcome(Health.UNHEALTHY, retryable=False),
                             f"no complete answer within {timeout:g}s")
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError, aiohttp.ClientPayloadError) as exc:
            return Exchange(ResultKind.SERVER_ERROR, AttemptOutcome(Health.UNHEALTHY, retryable=True),
                             f"connection dropped: {type(exc).__name__}: {exc}")
        except _BodyTooLarge:
            return Exchange(ResultKind.SERVER_ERROR, AttemptOutcome(Health.UNKNOWN, retryable=False),
                             f"answer larger than {cfg.max_body_bytes} bytes; not read")
        except aiohttp.ClientError as exc:
            return Exchange(ResultKind.SERVER_ERROR, AttemptOutcome(Health.UNHEALTHY, retryable=False),
                             f"not a valid HTTP answer: {type(exc).__name__}: {exc}")
        return interpret_answer(status, raw, retry_after)


async def _read_capped(stream: aiohttp.StreamReader, limit: int) -> bytes:
    chunks: List[bytes] = []
    size = 0
    async for chunk in stream.iter_chunked(_CHUNK):
        size += len(chunk)
        if size > limit:
            raise _BodyTooLarge(size)
        chunks.append(chunk)
    return b"".join(chunks)


def _json_object(raw: bytes) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def interpret_answer(status: int, raw: bytes, retry_after: Optional[float]) -> Exchange:
    """One HTTP answer from /api/generate. Shared with the sync path in fast_inference."""
    health, retryable = classify_status(status)
    outcome = AttemptOutcome(health, retryable, retry_after)
    data = _json_object(raw)
    if 200 <= status < 300:
        if data is None or not isinstance(data.get("response"), str):
            return Exchange(ResultKind.SERVER_ERROR, AttemptOutcome(Health.UNHEALTHY, retryable=False),
                             f"HTTP {status} with a body that is not an Ollama answer: {raw[:120]!r}",
                             status=status)
        text = data["response"].strip()
        count = data.get("eval_count")
        eval_count = count if isinstance(count, int) and not isinstance(count, bool) else 0
        done_reason = str(data.get("done_reason") or "")
        if not text:
            return Exchange(ResultKind.EMPTY, outcome,
                             f"HTTP {status} but the model generated nothing "
                             f"(done_reason={done_reason or 'unknown'!r})",
                             status=status, eval_count=eval_count, done_reason=done_reason)
        return Exchange(ResultKind.OK, outcome, text=text, status=status, eval_count=eval_count,
                         done_reason=done_reason)
    if data is not None and data.get("error"):
        message = str(data["error"])
    else:
        message = raw[:200].decode("utf-8", "replace").strip()
    if status in (429, 503):
        kind = ResultKind.BUSY
    elif health is Health.HEALTHY:
        kind = ResultKind.REJECTED
    else:
        kind = ResultKind.SERVER_ERROR
    return Exchange(kind, outcome, f"HTTP {status}: {message}", status=status)
