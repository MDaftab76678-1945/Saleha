"""
Verified search: draw candidates concurrently, stop at the first one an
independent check accepts.

Measured (pass 169): one qwen2.5-coder:3b repair attempt fixes the LIS bug
about 2 times in 10. A handful of attempts has a far better chance than one,
and model calls are I/O-bound, so they can overlap. What makes this safe is
that the winner is chosen by a verifier the caller supplies (tests plus a
brute-force comparison in the swarm), never by the candidate source.

Outcomes stay distinct: a candidate whose source or verifier crashed is
DID_NOT_RUN, a repeat of an earlier candidate is DUPLICATE, and only a
verifier's explicit PASSED can make `found` true. An empty budget finds
nothing; it is not a vacuous pass.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Protocol, Set

logger = logging.getLogger(__name__)


class Outcome(enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    DID_NOT_RUN = "did_not_run"  # the source or the verifier raised, or gave nothing
    DUPLICATE = "duplicate"  # same code as an earlier candidate; not re-verified


@dataclass(frozen=True)
class Verification:
    """What a verifier concluded about one candidate."""

    outcome: Outcome
    detail: str = ""

    def __post_init__(self) -> None:
        if self.outcome is Outcome.DUPLICATE:
            raise ValueError("DUPLICATE is assigned by the search, not by a verifier")


class CandidateSource(Protocol):
    """Produces candidate `index` (0-based). Empty text means it produced nothing."""

    def __call__(self, index: int, /) -> str: ...


class Verifier(Protocol):
    """Judges a candidate independently of whoever produced it."""

    def __call__(self, code: str, /) -> Verification: ...


@dataclass(frozen=True)
class CandidateOutcome:
    index: int
    code: str
    outcome: Outcome
    detail: str
    seconds: float


@dataclass
class SearchResult:
    winner: Optional[CandidateOutcome]
    outcomes: List[CandidateOutcome] = field(default_factory=list)
    budget: int = 0

    @property
    def found(self) -> bool:
        return self.winner is not None

    @property
    def attempted(self) -> int:
        return len(self.outcomes)

    def summary(self) -> str:
        counts = {o: sum(1 for c in self.outcomes if c.outcome is o) for o in Outcome}
        head = (f"candidate {self.winner.index + 1} passed" if self.winner
                else "no candidate passed")
        tail = ", ".join(f"{n} {o.value}" for o, n in counts.items() if n)
        return f"{head} ({self.attempted} of {self.budget} tried: {tail or 'none'})"


class VerifiedSearch:
    """
    Runs up to `budget` candidates, `concurrency` at a time, and returns the
    first one the verifier passes. Candidates not yet started when a winner
    appears are never started; ones already running finish but are ignored.
    """

    def __init__(self, source: CandidateSource, verifier: Verifier, *, budget: int,
                 concurrency: int = 1, known: Iterable[str] = (),
                 clock: Callable[[], float] = time.perf_counter) -> None:
        if budget < 0:
            raise ValueError(f"budget must be >= 0, got {budget}")
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")
        self._source = source
        self._verifier = verifier
        self._budget = budget
        self._concurrency = min(concurrency, budget) if budget else 1
        self._clock = clock
        # known: code already judged elsewhere (e.g. the code being repaired).
        self._seen: Set[str] = {k.strip() for k in known if k.strip()}
        self._seen_lock = threading.Lock()
        self._stop = threading.Event()

    def run(self) -> SearchResult:
        result = SearchResult(winner=None, budget=self._budget)
        if self._budget == 0:
            return result
        next_index = 0
        with ThreadPoolExecutor(max_workers=self._concurrency,
                                thread_name_prefix="verified-search") as pool:
            running: Set[Future[CandidateOutcome]] = set()
            while running or (next_index < self._budget and not self._stop.is_set()):
                while (len(running) < self._concurrency and next_index < self._budget
                       and not self._stop.is_set()):
                    running.add(pool.submit(self._attempt, next_index))
                    next_index += 1
                done, running = wait(running, return_when=FIRST_COMPLETED)
                # Sorted so the result does not depend on set iteration order.
                for fut in sorted(done, key=lambda f: f.result().index):
                    outcome = fut.result()
                    result.outcomes.append(outcome)
                    if outcome.outcome is Outcome.PASSED and result.winner is None:
                        result.winner = outcome
                        self._stop.set()
        result.outcomes.sort(key=lambda c: c.index)
        logger.info("verified search: %s", result.summary())
        return result

    def _attempt(self, index: int) -> CandidateOutcome:
        """Never raises: every failure becomes an outcome the caller can see."""
        start = self._clock()

        def done(code: str, outcome: Outcome, detail: str) -> CandidateOutcome:
            return CandidateOutcome(index, code, outcome, detail, self._clock() - start)

        try:
            code = self._source(index)
        except Exception as exc:  # noqa: BLE001 -- a crashing source must not end the search
            logger.warning("candidate %d: source raised %s: %s", index, type(exc).__name__, exc)
            return done("", Outcome.DID_NOT_RUN, f"source raised {type(exc).__name__}: {exc}")
        if not isinstance(code, str) or not code.strip():
            return done("", Outcome.DID_NOT_RUN, "source produced no code")

        key = code.strip()
        with self._seen_lock:
            if key in self._seen:
                return done(code, Outcome.DUPLICATE, "same code as an earlier candidate")
            self._seen.add(key)

        try:
            verdict = self._verifier(code)
        except Exception as exc:  # noqa: BLE001 -- a crashing verifier is "did not run", not "failed"
            logger.warning("candidate %d: verifier raised %s: %s", index, type(exc).__name__, exc)
            return done(code, Outcome.DID_NOT_RUN, f"verifier raised {type(exc).__name__}: {exc}")
        if not isinstance(verdict, Verification):
            return done(code, Outcome.DID_NOT_RUN,
                        f"verifier returned {type(verdict).__name__}, not a Verification")
        return done(code, verdict.outcome, verdict.detail)
