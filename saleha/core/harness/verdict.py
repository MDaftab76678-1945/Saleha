"""
Saleha Core: a test pass that only real execution can produce.

Why
---
Every fabricated pass in this repo's history had one root: "passed" was a
bool, and any code path could set it. The orchestrator returned success
without running the code; a smoke run with zero tests came back
`passed=True`; non-Python code "passed" its suite without the suite ever
running; `/autopr` printed "5/5 PASSED".

Here a pass is a `Verified` object -- the type-state idea from the NEXUS v7
notes, where `Task<Verified>` can only be built by the check itself. Its
constructor demands a token private to this module, so `Verified(...)`
anywhere else raises. The one function that issues it,
`judge_suite_output()`, reads the evidence itself: the per-run result line
in the process output, the exit code, and how many tests actually executed.
It also stores a digest of the exact code and tests it judged, so a pass for
one version cannot be carried over to another (`Verified.covers`).

Every other outcome is `NotVerified` with a kind. None is a pass, and the
three must never render the same:

  FAILED             tests ran and at least one failed, or the code crashed
  DID_NOT_RUN        nothing was judged: blocked, crashed or timed out before
                     reporting, unreadable result
  NOTHING_TO_VERIFY  it ran, but no test executed (no suite, an empty suite,
                     every test skipped, or no runner for the language)

Limits
------
Python has no private constructors. Code that deliberately imports `_MINT`,
or opens a ticket and forges its result line, can still lie. What this
removes is the accidental and the lazy fabrication -- `passed=True` typed
into a result -- and a deliberate one now has to name `_MINT` or `open_run`,
which grep finds.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Union

PASSED = "passed"
FAILED = "failed"
DID_NOT_RUN = "did_not_run"
NOTHING_TO_VERIFY = "nothing_to_verify"

RESULT_PREFIX = "SALEHA_TEST_JSON:"
NO_REPORT = "the suite crashed or timed out before reporting a result"

_MINT = object()
_MAX_OPEN_TICKETS = 4096
_open_tickets: "OrderedDict[str, None]" = OrderedDict()
_tickets_lock = threading.Lock()


def subject_digest(code: str, tests: str) -> str:
    """Identity of what was judged: the exact solution and test text."""
    return hashlib.sha256(f"{code}\0{tests}".encode("utf-8", "surrogatepass")).hexdigest()


@dataclass(frozen=True)
class RunTicket:
    """One execution's claim check. The nonce is fresh, so code under test
    cannot print a result line for it in advance."""

    nonce: str
    digest: str

    @property
    def marker(self) -> str:
        return f"{RESULT_PREFIX}{self.nonce}:"


def open_run(code: str, tests: str) -> RunTicket:
    ticket = RunTicket(secrets.token_hex(8), subject_digest(code, tests))
    with _tickets_lock:
        _open_tickets[ticket.nonce] = None
        while len(_open_tickets) > _MAX_OPEN_TICKETS:
            _open_tickets.popitem(last=False)  # runs abandoned before judging
    return ticket


def _redeem(ticket: RunTicket) -> bool:
    with _tickets_lock:
        return _open_tickets.pop(ticket.nonce, 0) is None


@dataclass(frozen=True)
class Failure:
    test: str
    traceback: str


class Verified:
    """A test suite really executed against this exact code and every
    executed test passed. Only `judge_suite_output()` can create one."""

    __slots__ = ("ran", "skipped", "digest")
    kind = PASSED
    failures: Tuple[Failure, ...] = ()
    reason = ""

    ran: int
    skipped: int
    digest: str

    def __init__(self, token: object, *, ran: int, skipped: int, digest: str) -> None:
        if token is not _MINT:
            raise TypeError("Verified is issued only by judge_suite_output(); a pass cannot be constructed")
        if ran - skipped < 1:
            raise ValueError("a pass needs at least one executed test")
        object.__setattr__(self, "ran", ran)
        object.__setattr__(self, "skipped", skipped)
        object.__setattr__(self, "digest", digest)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"Verified is immutable; cannot set {name} to {value!r}")

    def covers(self, code: str, tests: str) -> bool:
        """True only for the exact code and tests that were judged."""
        return self.digest == subject_digest(code, tests)

    def __repr__(self) -> str:
        return f"Verified(ran={self.ran}, skipped={self.skipped})"


@dataclass(frozen=True)
class NotVerified:
    kind: str
    reason: str
    ran: int = 0
    skipped: int = 0
    failures: Tuple[Failure, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in (FAILED, DID_NOT_RUN, NOTHING_TO_VERIFY):
            raise ValueError(f"NotVerified kind must be failed / did_not_run / nothing_to_verify, not {self.kind!r}")


Verdict = Union[Verified, NotVerified]


def _find_result_line(output: str, marker: str) -> Optional[str]:
    for line in reversed((output or "").splitlines()):
        line = line.strip()
        if line.startswith(marker):
            return line[len(marker):]
    return None


def judge_suite_output(ticket: RunTicket, output: str, exit_ok: bool) -> Verdict:
    """Read one run's evidence and decide. A ticket is judged once."""
    if not _redeem(ticket):
        return NotVerified(DID_NOT_RUN, "run ticket unknown or already judged; this output proves nothing")

    line = _find_result_line(output, ticket.marker)
    if line is None:
        return NotVerified(DID_NOT_RUN, NO_REPORT)
    try:
        payload = json.loads(line)
        ran = int(payload.get("ran", 0))
        skipped = int(payload.get("skipped", 0))
        failures = tuple(
            Failure(str(item.get("test", "<unknown>")), str(item.get("traceback", "")))
            for item in payload.get("failures", [])
        )
    except (ValueError, TypeError, AttributeError) as err:
        return NotVerified(DID_NOT_RUN, f"unreadable test result: {err}")

    if ran - skipped <= 0:
        why = f"; {failures[0].traceback}" if failures else ""
        return NotVerified(NOTHING_TO_VERIFY, f"test suite ran 0 tests -- nothing was verified{why}",
                           ran, skipped, failures)
    if failures:
        return NotVerified(FAILED, f"{len(failures)} of {ran} tests failed", ran, skipped, failures)
    if not exit_ok:
        return NotVerified(FAILED, "every test passed but the run exited non-zero", ran, skipped)
    return Verified(_MINT, ran=ran, skipped=skipped, digest=ticket.digest)
