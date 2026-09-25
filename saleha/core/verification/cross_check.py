"""
Cross-checking: choose among model-written solutions using model-written tests
without trusting any single test (CodeT-style dual agreement).

A 3B model writes wrong tests (real run: `assertFalse(is_palindrome("A"))`
for a case-insensitive task), so "the tests passed" means little on its own.
Here every candidate solution runs against every test suite. Candidates
that fail exactly the same tests agree with each other; a group scores
(group size) x (tests its members pass). A wrong test fails every correct
candidate alike, so it lowers every group equally instead of deciding the
winner, while a wrong solution rarely agrees with independent ones.

Nothing here is ground truth. `agreement` says how much support the winner
had; with one candidate or no passing test there is no winner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from saleha.core.harness.test_runner import TestRunner

Signature = Tuple[FrozenSet[str], ...]


@dataclass
class CrossCheckResult:
    winner_index: Optional[int]          # None: no candidate is supported
    winner_code: str
    group: List[int]                     # candidates that agree with the winner
    tests_passed_by_winner: int
    agreement: str                       # e.g. "3/5 candidates agree, pass 7 tests"
    reason: str = ""
    passes: Dict[int, int] = field(default_factory=dict)


def cross_check(candidates: List[str], suites: List[str],
                runner: Optional[TestRunner] = None, timeout: int = 15) -> CrossCheckResult:
    runner = runner or TestRunner()
    live = [(i, c) for i, c in enumerate(candidates) if c and c.strip()]
    suites = [s for s in suites if s and s.strip()]
    if len(live) < 2 or not suites:
        return CrossCheckResult(None, "", [], 0, "not cross-checked",
                                reason="needs at least 2 candidates and 1 test suite")

    signatures: Dict[int, Signature] = {}
    passes: Dict[int, int] = {}
    for i, code in live:
        sig = []
        passed = 0
        for suite in suites:
            run = runner.run_suite(code, test_code=suite, timeout=timeout)
            failed = frozenset(f.test_name for f in run.failures)
            if run.ran == 0:
                failed = frozenset({"<suite did not run>"})
            sig.append(failed)
            passed += max(0, run.ran - len(run.failures))
        signatures[i] = tuple(sig)
        passes[i] = passed

    groups: Dict[Signature, List[int]] = {}
    for i, sig in signatures.items():
        groups.setdefault(sig, []).append(i)

    best = max(groups.values(), key=lambda g: (len(g) * passes[g[0]], len(g), -g[0]))
    if passes[best[0]] == 0:
        return CrossCheckResult(None, "", [], 0, "no candidate passes any test",
                                reason="no support for any candidate", passes=passes)
    winner = best[0]
    return CrossCheckResult(
        winner_index=winner,
        winner_code=candidates[winner],
        group=best,
        tests_passed_by_winner=passes[winner],
        agreement=f"{len(best)}/{len(live)} candidates agree, pass {passes[winner]} tests",
        passes=passes,
    )
