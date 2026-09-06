"""
Saleha Core: Parallel Candidate Solving

The idea
--------
The orchestrator generates one candidate, tests it, and if it fails, heals
it -- each step a separate round trip. That is the right shape when calls
are expensive relative to compute, but on a local model the GPU is mostly
idle during prompt evaluation, which is why five concurrent calls take 15.5s
where five sequential ones take ~34s (measured, this box, qwen2.5-coder:3b).

So: generate several candidates at once and pick the one that actually
works. This is not "ask the model twice and hope" -- selection is done by
real execution against real tests, never by asking a model which answer it
likes. A model rating its own output is the same trust failure as a model
declaring itself finished, and that failure has already been measured here.

Why this is worth the extra tokens
----------------------------------
The failure mode of a small model is rarely "always wrong"; it is
"inconsistent". Measured earlier in this project: the same configuration,
the same task, run twice, produced tool calls one time and nothing the
next. Sampling three candidates and keeping the one that passes converts
that variance from a coin flip into an advantage -- but only because the
filter is execution, not opinion.

Honest cost
-----------
N candidates cost roughly N times the tokens and about 2x the wall time of
one (concurrency is sublinear -- one GPU). It is worth it when a wrong
answer is expensive to discover later, and wasteful for trivial tasks.
`should_parallelise()` encodes that judgement rather than leaving callers
to guess, and callers can override it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from saleha.core.fast_inference import (
    FastInference,
    InferenceRequest,
    InferenceResult,
)


@dataclass
class Candidate:
    """One generated attempt plus what actually happened when it ran."""

    index: int
    code: str
    raw: str = ""
    executed: bool = False
    passed: bool = False
    error: str = ""
    latency_sec: float = 0.0
    temperature: float = 0.0

    @property
    def usable(self) -> bool:
        return bool(self.code.strip())


@dataclass
class SolveResult:
    success: bool
    code: str = ""
    candidates: List[Candidate] = field(default_factory=list)
    chosen_index: int = -1
    reason: str = ""
    total_latency_sec: float = 0.0

    @property
    def verified(self) -> bool:
        """True only when the chosen candidate was proved by execution."""
        return (self.chosen_index >= 0
                and self.candidates[self.chosen_index].passed)


_CODE_FENCE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """
    Pull code out of a model reply.

    Prefers the largest fenced block -- models often emit a short usage
    example alongside the real implementation, and taking the first block
    grabs the example. Falls back to the raw text when unfenced.
    """
    blocks = _CODE_FENCE.findall(text or "")
    if blocks:
        return max(blocks, key=len).strip()
    return (text or "").strip()


def should_parallelise(goal: str, complexity: float = 0.0) -> bool:
    """
    Whether multiple candidates are worth the tokens for this task.

    Cheap heuristic, deliberately conservative: parallelism costs N times
    the tokens, so it should be reserved for work where a wrong answer is
    expensive to find later. Trivial one-liners do not qualify.
    """
    if complexity >= 5.0:
        return True
    words = len((goal or "").split())
    if words <= 6:
        return False
    hard = ("algorithm", "optimize", "concurrent", "async", "parser",
            "refactor", "thread", "cache", "recursive", "distributed")
    return any(h in (goal or "").lower() for h in hard)


class ParallelSolver:
    """
    Generate several candidates concurrently, keep the one that passes.

    The verifier is injected. It must be something that really runs the
    code -- a sandboxed executor, a test command -- never a model asked for
    an opinion. Without a verifier this falls back to a structural
    heuristic and says so in `reason`, so a caller can never mistake an
    unverified pick for a proved one.
    """

    def __init__(self, inference: Optional[FastInference] = None,
                 model: str = "qwen2.5-coder:3b",
                 candidates: int = 3,
                 temperatures: Optional[Sequence[float]] = None):
        self.inference = inference or FastInference()
        self.model = model
        self.n = max(1, candidates)
        # Varied temperatures, not N identical samples: at temperature 0 the
        # same prompt yields the same answer, so N copies would cost N times
        # the tokens for exactly one distinct candidate.
        self.temperatures = list(temperatures or [0.0, 0.3, 0.7])[:self.n]
        while len(self.temperatures) < self.n:
            self.temperatures.append(0.5)

    def _build_requests(self, goal: str, context: str = "") -> List[InferenceRequest]:
        prompt = (
            f"{context}\n\n" if context else ""
        ) + (
            f"Write complete, runnable Python for this task:\n\n{goal}\n\n"
            "Reply with one ```python code block and nothing else."
        )
        return [
            InferenceRequest(prompt=prompt, model=self.model,
                             options={"temperature": t, "num_predict": 1200},
                             tag=f"cand{i}")
            for i, t in enumerate(self.temperatures)
        ]

    def solve(self, goal: str, context: str = "",
              verifier: Optional[Callable[[str], tuple]] = None) -> SolveResult:
        """
        Generate candidates concurrently and return the first that verifies.

        `verifier(code) -> (passed: bool, detail: str)` must actually run
        the code. Candidates are checked in generation order so the result
        is deterministic given the same replies -- otherwise two runs over
        identical candidates could disagree, which would make the whole
        thing untrustworthy.
        """
        reqs = self._build_requests(goal, context)
        # Caching is disabled here on purpose: the point is N *different*
        # candidates, and a warm cache would return the same one N times.
        results: List[InferenceResult] = self.inference.run_batch(reqs, use_cache=False)
        total = sum(r.latency_sec for r in results)

        candidates: List[Candidate] = []
        for i, r in enumerate(results):
            candidates.append(Candidate(
                index=i,
                code=extract_code(r.content) if r.success else "",
                raw=r.content if r.success else "",
                error="" if r.success else r.error,
                latency_sec=r.latency_sec,
                temperature=self.temperatures[i] if i < len(self.temperatures) else 0.0,
            ))

        usable = [c for c in candidates if c.usable]
        if not usable:
            return SolveResult(success=False, candidates=candidates,
                               reason="no candidate produced any code",
                               total_latency_sec=round(total, 2))

        if verifier is not None:
            for c in usable:
                try:
                    passed, detail = verifier(c.code)
                except Exception as exc:
                    passed, detail = False, f"verifier raised: {exc}"
                c.executed = True
                c.passed = bool(passed)
                if not c.passed:
                    c.error = str(detail)[:400]
                if c.passed:
                    return SolveResult(
                        success=True, code=c.code, candidates=candidates,
                        chosen_index=c.index,
                        reason=f"candidate {c.index} (temp {c.temperature}) "
                               f"verified by execution",
                        total_latency_sec=round(total, 2))

            # Nothing passed. Returning a candidate anyway would be handing
            # back an unverified answer under a success flag.
            return SolveResult(
                success=False, candidates=candidates,
                reason=f"all {len(usable)} candidates failed verification",
                total_latency_sec=round(total, 2))

        # No verifier: pick structurally and label the pick as unverified.
        best = max(usable, key=lambda c: (
            c.code.count("def "), c.code.count("\n"), -c.index))
        return SolveResult(
            success=True, code=best.code, candidates=candidates,
            chosen_index=best.index,
            reason=("no verifier supplied -- picked structurally, "
                    "NOT proved to work"),
            total_latency_sec=round(total, 2))

    def solve_with_executor(self, goal: str, test_suite: str,
                            context: str = "") -> SolveResult:
        """
        Convenience wrapper: verify each candidate by really running it
        against a real test suite in the sandboxed executor.
        """
        from saleha.core.code_executor import CodeExecutor

        executor = CodeExecutor(timeout=15)

        def verify(code: str):
            res = executor.execute(f"{code}\n\n{test_suite}")
            ok = bool(getattr(res, "success", False))
            out = getattr(res, "output", "") or ""
            # A suite that prints a marker is only passing if the marker
            # appears; exit code alone can be 0 for a suite that ran nothing.
            if ok and "TEST_PASSED" in test_suite:
                ok = "TEST_PASSED" in out
            return ok, (getattr(res, "error", "") or out)[:400]

        return self.solve(goal, context=context, verifier=verify)
