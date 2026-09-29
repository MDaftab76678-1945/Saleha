"""
Circuit breaker, retry policy and HTTP failure classification for calls to a
model server.

Why: when Ollama is down or wedged, every model call paid the full cost of
failing again. On this machine a refused connection costs ~2 s (~4 s through
`localhost`, which tries ::1 first), a hung generation costs the full
SALEHA_MODEL_TIMEOUT, and FastInference retried even timed-out generations.
After a few consecutive failures the breaker answers "not sent: circuit open"
at once, then lets a single probe through after a cool-down.

Design:
- The transition logic is pure. `admit_call()` and `record_result()` take a
  frozen `BreakerSnapshot` and return a new one, so the logic holds no state
  and is tested without clocks or threads.
- State lives in a `BreakerStore`, which applies such a function atomically.
  `InMemoryBreakerStore` serves one process; a store shared between
  processes only has to implement the same three methods.
- `CircuitBreaker` binds a policy, a store and a clock, and holds nothing
  else.

Outcomes are never merged:
- An HTTP 4xx proves the server is answering, so it does not count against it.
- A cancelled call gives its probe slot back without judging the server.
- Only the current round's probe decides whether an open circuit closes.
"""

from __future__ import annotations

import enum
import logging
import math
import os
import random
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Optional, Protocol, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class Health(enum.Enum):
    """What one finished call says about the server."""

    HEALTHY = "healthy"  # answered like a working server (2xx, or a 4xx about the request)
    UNHEALTHY = "unhealthy"  # refused, reset, timed out, 5xx, 408/429
    UNKNOWN = "unknown"  # says nothing about the server: cancelled, or a local error


@dataclass(frozen=True)
class BreakerPolicy:
    failure_threshold: int = 3  # consecutive UNHEALTHY results that open the circuit
    open_seconds: float = 30.0  # cool-down before a probe is let through
    half_open_probes: int = 1  # probes allowed at once while half-open

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {self.failure_threshold}")
        if not (self.open_seconds > 0 and math.isfinite(self.open_seconds)):
            raise ValueError(f"open_seconds must be a positive number, got {self.open_seconds}")
        if self.half_open_probes < 1:
            raise ValueError(f"half_open_probes must be >= 1, got {self.half_open_probes}")


@dataclass(frozen=True)
class BreakerSnapshot:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0  # consecutive UNHEALTHY results while closed
    opened_at: float = 0.0
    # Bumped on every OPEN -> HALF_OPEN move, so a late probe from an earlier
    # round cannot decide the current one.
    epoch: int = 0
    probes: int = 0  # probes in flight in the current half-open round
    last_error: str = ""


@dataclass(frozen=True)
class Admission:
    allowed: bool
    probe: bool = False
    epoch: int = 0
    retry_after: float = 0.0  # seconds until a call can be admitted; 0 when unknown
    reason: str = ""


def admit_call(snap: BreakerSnapshot, now: float,
               policy: BreakerPolicy) -> Tuple[BreakerSnapshot, Admission]:
    """Decide whether a call may go out now. Pure."""
    if snap.state is CircuitState.CLOSED:
        return snap, Admission(True)
    if snap.state is CircuitState.OPEN:
        wait = snap.opened_at + policy.open_seconds - now
        if wait > 0:
            return snap, Admission(False, retry_after=wait,
                                   reason=f"circuit open after {snap.failures} failure(s): {snap.last_error}")
        snap = replace(snap, state=CircuitState.HALF_OPEN, epoch=snap.epoch + 1, probes=0)
    if snap.probes >= policy.half_open_probes:
        return snap, Admission(False, reason=f"circuit half-open, a probe is in flight after: {snap.last_error}")
    snap = replace(snap, probes=snap.probes + 1)
    return snap, Admission(True, probe=True, epoch=snap.epoch)


def record_result(snap: BreakerSnapshot, admission: Admission, health: Health, now: float,
                  policy: BreakerPolicy, detail: str = "") -> BreakerSnapshot:
    """Fold one finished call into the state. Pure."""
    if admission.probe and snap.state is CircuitState.HALF_OPEN and admission.epoch == snap.epoch:
        if health is Health.HEALTHY:
            return BreakerSnapshot(epoch=snap.epoch)
        if health is Health.UNHEALTHY:
            return replace(snap, state=CircuitState.OPEN, opened_at=now, probes=0, failures=snap.failures + 1,
                           last_error=detail or snap.last_error)
        return replace(snap, probes=max(0, snap.probes - 1))  # UNKNOWN: hand the slot back
    if snap.state is not CircuitState.CLOSED:
        return snap  # results of calls admitted earlier do not decide an open circuit
    if health is Health.HEALTHY:
        return snap if not (snap.failures or snap.last_error) else replace(snap, failures=0, last_error="")
    if health is Health.UNHEALTHY:
        failures = snap.failures + 1
        if failures >= policy.failure_threshold:
            return replace(snap, state=CircuitState.OPEN, failures=failures, opened_at=now, last_error=detail)
        return replace(snap, failures=failures, last_error=detail)
    return snap


class BreakerStore(Protocol):
    def transact(self, key: str, fn: Callable[[BreakerSnapshot], Tuple[BreakerSnapshot, T]]) -> T:
        """Apply `fn` to the snapshot for `key` atomically, keep its new snapshot, return its value."""
        ...

    def get(self, key: str) -> BreakerSnapshot: ...

    def clear(self) -> None: ...


class InMemoryBreakerStore:
    """For one process. The lock is held only for the pure step, never across I/O."""

    def __init__(self) -> None:
        self._data: Dict[str, BreakerSnapshot] = {}
        self._lock = threading.Lock()

    def transact(self, key: str, fn: Callable[[BreakerSnapshot], Tuple[BreakerSnapshot, T]]) -> T:
        with self._lock:
            new, value = fn(self._data.get(key, BreakerSnapshot()))
            self._data[key] = new
            return value

    def get(self, key: str) -> BreakerSnapshot:
        with self._lock:
            return self._data.get(key, BreakerSnapshot())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class CircuitBreaker:
    """Binds a policy, a store and a clock. Holds no state of its own."""

    def __init__(self, policy: Optional[BreakerPolicy] = None, store: Optional[BreakerStore] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.policy = policy or BreakerPolicy()
        self.store: BreakerStore = store if store is not None else InMemoryBreakerStore()
        self._clock = clock

    def admit(self, key: str) -> Admission:
        now = self._clock()
        admission = self.store.transact(key, lambda snap: admit_call(snap, now, self.policy))
        if admission.probe:
            logger.info("circuit %s half-open: letting one probe through", key)
        return admission

    def record(self, key: str, admission: Admission, health: Health, detail: str = "") -> BreakerSnapshot:
        now = self._clock()

        def step(snap: BreakerSnapshot) -> Tuple[BreakerSnapshot, Tuple[BreakerSnapshot, BreakerSnapshot]]:
            new = record_result(snap, admission, health, now, self.policy, detail)
            return new, (snap, new)

        before, after = self.store.transact(key, step)
        if before.state is not after.state:
            if after.state is CircuitState.OPEN:
                logger.warning("circuit %s opened for %.0fs: %s", key, self.policy.open_seconds, after.last_error)
            else:
                logger.info("circuit %s %s", key, after.state.value)
        return after

    def snapshot(self, key: str) -> BreakerSnapshot:
        return self.store.get(key)


# -- retry policy ----------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3  # total tries, the first one included
    base_delay: float = 0.5
    max_delay: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if not (0 <= self.base_delay <= self.max_delay and math.isfinite(self.max_delay)):
            raise ValueError(f"need 0 <= base_delay <= max_delay, got {self.base_delay}, {self.max_delay}")

    def backoff(self, retry: int, rng: random.Random, retry_after: Optional[float] = None) -> float:
        """Delay before retry number `retry` (1-based): the server's Retry-After, else full jitter."""
        if retry_after is not None:
            return min(retry_after, self.max_delay)
        ceiling = min(self.max_delay, self.base_delay * 2.0 ** min(retry - 1, 60))
        return rng.uniform(0.0, ceiling)


@dataclass(frozen=True)
class AttemptOutcome:
    health: Health
    retryable: bool
    retry_after: Optional[float] = None


def next_delay(policy: RetryPolicy, attempt: int, outcome: AttemptOutcome, remaining: float,
               rng: random.Random) -> Optional[float]:
    """Seconds to wait before another attempt, or None to stop. Never sleeps past the deadline."""
    if not outcome.retryable or attempt >= policy.max_attempts:
        return None
    delay = policy.backoff(attempt, rng, outcome.retry_after)
    return delay if delay < remaining else None


# -- HTTP classification ---------------------------------------------------


def classify_status(status: int) -> Tuple[Health, bool]:
    """(what the status says about the server, whether a retry can help)."""
    if 200 <= status < 300:
        return Health.HEALTHY, False
    if status in (408, 429):
        return Health.UNHEALTHY, True
    if 400 <= status < 500:
        return Health.HEALTHY, False  # the request was wrong; the server is fine
    if status in (502, 503, 504):
        return Health.UNHEALTHY, True
    if 500 <= status < 600:
        return Health.UNHEALTHY, False  # often this input; retrying repeats it
    return Health.UNKNOWN, False  # 1xx/3xx: not an answer an API gives


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Retry-After in seconds. HTTP-date values and nonsense give None."""
    try:
        seconds = float((value or "").strip())
    except ValueError:
        return None
    return seconds if 0 <= seconds < math.inf else None


# -- process-wide breaker ---------------------------------------------------

_shared: Optional[CircuitBreaker] = None
_shared_lock = threading.Lock()


def _policy_from_env() -> BreakerPolicy:
    try:
        return BreakerPolicy(failure_threshold=int(os.environ.get("SALEHA_BREAKER_FAILURES", "3")),
                             open_seconds=float(os.environ.get("SALEHA_BREAKER_OPEN_SECONDS", "30")))
    except ValueError as exc:
        logger.warning("ignoring SALEHA_BREAKER_* settings (%s); using the defaults", exc)
        return BreakerPolicy()


def shared_breaker() -> CircuitBreaker:
    """The breaker every model-server client in this process shares, keyed by base URL."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = CircuitBreaker(_policy_from_env())
        return _shared


def reset_shared_breaker() -> None:
    """Forget all recorded failures. Objects holding the shared breaker keep working."""
    shared_breaker().store.clear()
