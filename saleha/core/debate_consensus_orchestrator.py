"""
Saleha Core: Multi-Agent Debate & Consensus Council

Runs a structured dialectic across four specialist personas plus an arbiter:
1. Advocate            -- argues for the strongest version of the proposal
2. Devil's Advocate    -- attacks the hidden assumptions
3. Security Red-Teamer -- threat model and blast radius
4. FinOps / SRE        -- cost, tail latency, operability
5. Arbiter             -- synthesises an ADR from what was actually said

What changed and why
--------------------
This module used to call no model at all. `__init__` was `pass`, and
`conduct_architectural_debate` returned f-string templates: every topic got
the same four "critiques" with the topic pasted in, always chose `opts[0]`,
and always reported "ACCEPTED (Consensus Confidence: 94.8%)". Two unrelated
topics produced byte-identical reasoning and the same 0.948 score, and
`saleha debate "Should we rewrite the CLI in Rust"` printed
"Adopted Option A (Should)" -- the option name was the first word of the
topic. Presenting that as a security review is worse than printing nothing.

Now each persona is a real model call. The three critics within a round are
independent of each other, so they are issued concurrently through
FastInference; the advocate must run first because the critics respond to it,
and the arbiter last because it reads the whole transcript. That ordering is
a real data dependency, not a performance choice.

Confidence is derived from what happened -- how many personas actually
answered -- not asserted. If the model is unreachable, the verdict says so
and confidence is 0.0 rather than 94.8%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from saleha.core.fast_inference import FastInference, InferenceRequest

DEFAULT_MODEL = "qwen2.5-coder:3b"


@dataclass
class DebateRound:
    round_number: int
    advocate_argument: str
    skeptic_rebuttal: str
    security_critique: str
    finops_impact: str

    @property
    def complete(self) -> bool:
        """All four positions were really produced by a model."""
        return all(v.strip() and not v.startswith("[unavailable")
                   for v in (self.advocate_argument, self.skeptic_rebuttal,
                             self.security_critique, self.finops_impact))


@dataclass
class DebateVerdict:
    topic: str
    rounds_conducted: int
    rounds: List[DebateRound]
    consensus_decision: str
    adr_markdown: str
    elo_confidence_score: float          # 0.0-1.0, derived from participation
    key_tradeoffs: List[str] = field(default_factory=list)
    degraded: bool = False               # True if any persona failed to answer
    errors: List[str] = field(default_factory=list)


# Persona instructions. Each critic is told to attack a different axis so the
# round produces genuinely different objections rather than three rewordings.
_CRITICS = {
    "skeptic": ("You are a Devil's Advocate. Attack the hidden assumptions and "
                "failure modes in the proposal below. Be concrete and brief."),
    "security": ("You are a security red-teamer. Give the threat model, trust "
                 "boundaries and blast radius of the proposal below. Be brief."),
    "finops": ("You are an SRE/FinOps reviewer. Give the cost, tail-latency and "
               "operability consequences of the proposal below. Be brief."),
}

_UNAVAILABLE = "[unavailable: {}]"


class DebateConsensusOrchestrator:
    """Multi-persona architectural debate. Every position is model-generated."""

    def __init__(self, model: str = DEFAULT_MODEL,
                 inference: Optional[Any] = None):
        self.model = model
        # Injected in tests; built lazily so importing this module opens no
        # connection.
        self.inference = inference

    def _engine(self) -> FastInference:
        if self.inference is None:
            self.inference = FastInference()
        return self.inference

    def _one(self, prompt: str, tag: str, tokens: int = 400) -> str:
        r = self._engine().run(InferenceRequest(
            prompt=prompt, model=self.model, tag=tag,
            options={"temperature": 0.4, "num_predict": tokens}))
        return r.content.strip() if r.success and r.content.strip() \
            else _UNAVAILABLE.format(r.error or "empty reply")

    def conduct_architectural_debate(
        self,
        topic: str,
        options: Optional[List[str]] = None,
        num_rounds: int = 2,
    ) -> DebateVerdict:
        """Run the debate. Each round: advocate, then three critics in parallel."""
        opts = list(options or [])
        rounds: List[DebateRound] = []
        errors: List[str] = []
        transcript: List[str] = []

        for r in range(1, max(1, num_rounds) + 1):
            prior = ("\n\nPrevious round:\n" + "\n".join(transcript[-3:])) \
                if transcript else ""
            advocate = self._one(
                f"You are an advocate. Argue for the strongest version of this "
                f"proposal, in a short paragraph.\n\nProposal: {topic}"
                f"{prior}\n\nAddress the objections above if there are any.",
                tag=f"advocate_r{r}")

            # The three critics all respond to the same advocate text and not
            # to each other, so they are genuinely independent -> run together.
            reqs = [
                InferenceRequest(
                    prompt=f"{instr}\n\nProposal: {topic}\n\n"
                           f"Advocate's case:\n{advocate}",
                    model=self.model, tag=name,
                    options={"temperature": 0.4, "num_predict": 400})
                for name, instr in _CRITICS.items()
            ]
            replies = {res.tag: res
                       for res in self._engine().run_batch(reqs, use_cache=False)}

            def text(name: str) -> str:
                res = replies.get(name)
                if res is None:
                    return _UNAVAILABLE.format("no reply")
                if res.success and res.content.strip():
                    return res.content.strip()
                errors.append(f"round {r} {name}: {res.error or 'empty reply'}")
                return _UNAVAILABLE.format(res.error or "empty reply")

            rnd = DebateRound(
                round_number=r,
                advocate_argument=advocate,
                skeptic_rebuttal=text("skeptic"),
                security_critique=text("security"),
                finops_impact=text("finops"),
            )
            if advocate.startswith("[unavailable"):
                errors.append(f"round {r} advocate: no reply")
            rounds.append(rnd)
            transcript.append(f"Round {r} objections: {rnd.skeptic_rebuttal[:300]}")

        # Confidence is measured participation, not a flattering constant.
        slots = max(1, len(rounds) * 4)
        answered = sum(1 for rd in rounds
                       for v in (rd.advocate_argument, rd.skeptic_rebuttal,
                                 rd.security_critique, rd.finops_impact)
                       if v.strip() and not v.startswith("[unavailable"))
        confidence = round(answered / slots, 3)
        degraded = answered < slots

        if answered == 0:
            adr = (f"# ADR: {topic}\n\n## Status\n**NO DECISION** -- the debate "
                   f"could not run; no persona returned a response.\n")
            return DebateVerdict(
                topic=topic, rounds_conducted=len(rounds), rounds=rounds,
                consensus_decision="No decision: the model was unreachable.",
                adr_markdown=adr, elo_confidence_score=0.0,
                key_tradeoffs=[], degraded=True, errors=errors)

        arbiter = self._one(
            "You are the arbiter of a technical debate. Using ONLY the "
            "positions below, write an Architecture Decision Record with the "
            "sections: Context, Options, Decision, Consequences. State the "
            "decision plainly. If the arguments do not settle it, say so.\n\n"
            f"Topic: {topic}\n"
            + (f"Options under consideration: {', '.join(opts)}\n" if opts else "")
            + "\n" + "\n\n".join(
                f"Round {rd.round_number}\n"
                f"Advocate: {rd.advocate_argument}\n"
                f"Skeptic: {rd.skeptic_rebuttal}\n"
                f"Security: {rd.security_critique}\n"
                f"FinOps: {rd.finops_impact}"
                for rd in rounds),
            tag="arbiter", tokens=900)

        if arbiter.startswith("[unavailable"):
            errors.append("arbiter: no reply")
            degraded = True
            adr = (f"# ADR: {topic}\n\n## Status\n**NO DECISION** -- personas "
                   f"responded but the arbiter did not.\n")
            decision = "No decision: the arbiter did not respond."
        else:
            # Only a top-level `# ` heading is a document title; a reply that
            # opens with `## Decision` is a section and still needs one.
            has_title = arbiter.lstrip().startswith("# ")
            adr = arbiter if has_title \
                else f"# Architecture Decision Record: {topic}\n\n{arbiter}"
            decision = self._first_meaningful_line(arbiter)

        tradeoffs = [rd.skeptic_rebuttal.strip().splitlines()[0][:160]
                     for rd in rounds
                     if rd.skeptic_rebuttal.strip()
                     and not rd.skeptic_rebuttal.startswith("[unavailable")]

        return DebateVerdict(
            topic=topic, rounds_conducted=len(rounds), rounds=rounds,
            consensus_decision=decision, adr_markdown=adr,
            elo_confidence_score=confidence, key_tradeoffs=tradeoffs,
            degraded=degraded, errors=errors)

    # Section titles that are never the decision itself. Matched against the
    # de-marked line, lowercased -- an early version returned "Architecture
    # Decision Record", the document heading, as the consensus decision.
    _NOT_A_DECISION = (
        "architecture decision record", "adr", "context", "options",
        "decision", "consequences", "status", "background", "summary",
        "positive", "negative", "options evaluated", "options considered",
    )

    @classmethod
    def _first_meaningful_line(cls, text: str) -> str:
        """
        The decision sentence from the ADR.

        Prefers the first prose line under a `Decision` heading; falls back to
        the first line that is not a heading or boilerplate title.
        """
        lines = (text or "").splitlines()

        def clean(ln: str) -> str:
            return ln.strip().lstrip("#*->0123456789. ").strip().rstrip("*").strip()

        def is_title(ln: str) -> bool:
            c = clean(ln).lower().rstrip(":").strip()
            return (not c) or c in cls._NOT_A_DECISION

        # Prefer the body of the Decision section.
        for i, ln in enumerate(lines):
            if clean(ln).lower().rstrip(":").strip() == "decision":
                for nxt in lines[i + 1:]:
                    if nxt.strip().startswith("#"):
                        break            # next section began; no prose found
                    if not is_title(nxt) and len(clean(nxt)) > 20:
                        return clean(nxt)[:300]
                break

        for ln in lines:
            if not is_title(ln) and len(clean(ln)) > 20:
                return clean(ln)[:300]
        return (text or "").strip()[:300] or "No decision recorded."


# Shared instance. Tests and benchmarks should build their own so they do not
# share an inference cache.
debate_orchestrator = DebateConsensusOrchestrator()
