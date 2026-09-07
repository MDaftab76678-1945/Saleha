"""
Saleha Core: Multi-Agent Architectural Council & Debate Engine

Three specialised personas analyse ONE problem from three different angles:
  1. Security Specialist   (attack surface, crypto, input validation)
  2. Performance Optimizer (time/space complexity, caching, I/O)
  3. Senior Architect      (modularity, testability, coupling)

Each writes a proposal for THIS problem, scores its own proposal on four
dimensions, then critiques the other two. The highest scorer wins and its
code is the consensus output.

## What this used to be

Every method in this module returned a constant. `generate_proposals()`
returned three hand-written HMAC/LRU/Protocol snippets with the problem
string interpolated into a comment; the scores (98/85/90/88, 88/99/92/95,
90/88/98/90) were literals; `critique_proposals()` returned six fixed
sentences naming those snippets; and `debate_and_synthesize()` emitted a
fixed `HighThroughputService` class. Measured:

    debate_and_synthesize("Design a distributed rate limiter")
    debate_and_synthesize("Write a haiku about frogs")

    -> byte-identical consensus_code (modulo the echoed problem string)
    -> byte-identical trade_off_analysis
    -> same winner, same 93.3/100, for both

The Performance Optimizer won every debate ever run, because 99 was the
largest literal in the file. `saleha council "<anything>"` printed HMAC
signature-validation boilerplate and called it a 93.3/100 consensus.

The debate structure was never the problem -- three framings genuinely do
pull a model toward different designs. What was missing is that anything
was asked at all. Each persona now writes its proposal and scores it, the
critiques quote the proposals actually generated, and a persona whose call
failed keeps score 0 so it cannot win by default.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class CouncilProposal:
    persona_name: str
    perspective: str
    proposed_code: str
    key_arguments: List[str]
    security_score: int        # 0 - 100
    performance_score: int     # 0 - 100
    maintainability_score: int # 0 - 100
    simplicity_score: int      # 0 - 100
    # False when the model call for this persona failed or returned
    # unparseable output. Such a proposal keeps every score at 0 so it can
    # never win, and the result reports it rather than hiding it.
    analysed: bool = True

    @property
    def overall_score(self) -> float:
        return round(
            (self.security_score * 0.3) +
            (self.performance_score * 0.3) +
            (self.maintainability_score * 0.25) +
            (self.simplicity_score * 0.15),
            1
        )


@dataclass
class CouncilDebateResult:
    problem_statement: str
    proposals: List[CouncilProposal]
    winning_persona: str
    consensus_code: str
    trade_off_analysis: str
    duration_sec: float
    total_consensus_score: float
    # True when no persona produced a usable proposal -- the caller is being
    # told the council failed, not handed a fabricated consensus.
    degenerate: bool = False
    # True when the top score is shared. The "winner" is then just the first
    # persona in order, which is a tie-break, not a judgement.
    tied: bool = False
    tied_personas: List[str] = field(default_factory=list)
    # Personas whose model call failed, by name.
    failed_personas: List[str] = field(default_factory=list)


class AgentCouncil:
    """Orchestrates multi-agent debate and consensus synthesis."""

    # Persona framings. These bias the model toward genuinely different
    # designs; the model still writes the proposal for THIS problem. These
    # are prompt inputs, not stored answers -- the previous version shipped
    # the answers themselves as constants.
    PERSONAS: List[Tuple[str, str, str]] = [
        ("\U0001f6e1️ Security Specialist", "Zero-Trust & Cryptographic Hardening",
         "Attack surface, input validation, authentication, secrets handling, "
         "and safe failure modes."),
        ("⚡ Performance Optimizer", "High-Throughput & Efficient Resource Use",
         "Time and space complexity, caching, allocation, I/O and contention."),
        ("\U0001f3db️ Senior Architect", "Clean Architecture & Maintainability",
         "Module boundaries, coupling, testability, and clarity of the design."),
    ]

    _PROPOSAL_SCHEMA = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "key_arguments": {"type": "array", "items": {"type": "string"}},
            "security_score": {"type": "number"},
            "performance_score": {"type": "number"},
            "maintainability_score": {"type": "number"},
            "simplicity_score": {"type": "number"},
        },
        "required": ["code", "key_arguments", "security_score",
                     "performance_score", "maintainability_score",
                     "simplicity_score"],
    }

    _CRITIQUE_SCHEMA = {
        "type": "object",
        "properties": {
            "critiques": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["critiques"],
    }

    def __init__(self, model: str = "auto", inference: Any = None):
        self.model = model
        self.inference = inference

    # -- infrastructure -----------------------------------------------------

    def _engine_and_model(self):
        from saleha.core.fast_inference import FastInference
        engine = self.inference or FastInference()
        model = self.model if self.model and self.model != "auto" \
            else "qwen2.5-coder:3b"
        return engine, model

    @staticmethod
    def _clamp_score(value: Any) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _strip_code_fence(code: str) -> str:
        """
        Drop a wrapping ```lang ... ``` fence if the model emitted one.

        The JSON schema asks for code, but a code-tuned model often returns it
        fenced anyway. Leaving the fence in means the consensus output is not
        directly runnable, so it is stripped -- only when it actually wraps
        the whole block, so fenced examples inside a longer answer survive.
        """
        text = code.strip()
        if not text.startswith("```"):
            return text
        newline = text.find("\n")
        if newline == -1:
            return text
        body = text[newline + 1:]
        end = body.rfind("```")
        return (body[:end] if end != -1 else body).strip()

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(content)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    # -- phase 1: proposals -------------------------------------------------

    def generate_proposals(self, problem: str) -> List[CouncilProposal]:
        """
        Three real proposals for THIS problem, generated concurrently.

        The three personas are independent of one another, so they go out in
        one batch. Each scores its own proposal on all four dimensions --
        including the ones it does not specialise in, which is what lets a
        security-hardened design honestly rate itself low on simplicity. The
        old literal scores could not make that judgement.
        """
        from saleha.core.fast_inference import InferenceRequest

        engine, model = self._engine_and_model()

        reqs = [
            InferenceRequest(
                prompt=(
                    "You are the " + name + " on an architecture council. "
                    "Propose a solution to this problem from your perspective "
                    "and reply as JSON.\n\n"
                    "Problem: " + problem + "\n\n"
                    "Your focus: " + focus + "\n\n"
                    "`code`: your concrete implementation for THIS problem. "
                    "`key_arguments`: 2-4 short reasons your approach is right "
                    "for THIS problem. Then score YOUR OWN proposal 0-100 on "
                    "each of `security_score`, `performance_score`, "
                    "`maintainability_score`, `simplicity_score`. Score "
                    "honestly -- a hardened design is often not the simplest, "
                    "and a fast one is often not the most maintainable."
                ),
                model=model,
                options={"temperature": 0.3, "num_predict": 900},
                response_format=self._PROPOSAL_SCHEMA,
                tag=name,
            )
            for name, _persp, focus in self.PERSONAS
        ]
        results = engine.run_batch(reqs, use_cache=False)

        proposals: List[CouncilProposal] = []
        for (name, perspective, focus), res in zip(self.PERSONAS, results):
            data = self._parse_json(res.content) if res.success else {}
            code = self._strip_code_fence(str(data.get("code") or ""))
            if not code:
                # Nothing was analysed. Record the failure at score 0 rather
                # than substituting a template -- a proposal that does not
                # exist must not be able to win the debate.
                proposals.append(CouncilProposal(
                    persona_name=name,
                    perspective=perspective,
                    proposed_code="",
                    key_arguments=[],
                    security_score=0,
                    performance_score=0,
                    maintainability_score=0,
                    simplicity_score=0,
                    analysed=False,
                ))
                continue
            args = [str(a) for a in (data.get("key_arguments") or [])][:4]
            proposals.append(CouncilProposal(
                persona_name=name,
                perspective=perspective,
                proposed_code=code,
                key_arguments=args,
                security_score=self._clamp_score(data.get("security_score")),
                performance_score=self._clamp_score(data.get("performance_score")),
                maintainability_score=self._clamp_score(data.get("maintainability_score")),
                simplicity_score=self._clamp_score(data.get("simplicity_score")),
                analysed=True,
            ))
        return proposals

    # -- phase 2: critique --------------------------------------------------

    def critique_proposals(
        self, proposals: List[CouncilProposal]
    ) -> Dict[str, List[str]]:
        """
        Each persona critiques the proposals the others actually wrote.

        The previous version returned six fixed sentences that named the
        hardcoded snippets, so the "adversarial critique" stayed word-for-word
        identical no matter what was proposed. Here each persona is shown the
        other two proposals' real code and answers about that code.

        A persona with nothing to critique (the others failed) gets an empty
        list rather than an invented objection.
        """
        from saleha.core.fast_inference import InferenceRequest

        engine, model = self._engine_and_model()
        critiques: Dict[str, List[str]] = {p.persona_name: [] for p in proposals}

        analysed = [p for p in proposals if p.analysed]
        if len(analysed) < 2:
            return critiques

        focus_by_name = {name: focus for name, _p, focus in self.PERSONAS}
        pending: List[Tuple[str, Any]] = []
        for critic in analysed:
            others = [p for p in analysed if p.persona_name != critic.persona_name]
            if not others:
                continue
            others_blob = "\n\n".join(
                "--- " + o.persona_name + " (" + o.perspective + ") ---\n"
                + o.proposed_code[:1200]
                for o in others
            )
            pending.append((critic.persona_name, InferenceRequest(
                prompt=(
                    "You are the " + critic.persona_name + " on an architecture "
                    "council. Critique the other members' proposals from your "
                    "perspective and reply as JSON.\n\n"
                    "Your focus: " + focus_by_name.get(critic.persona_name, "") + "\n\n"
                    "Their proposals:\n" + others_blob + "\n\n"
                    "`critiques`: one specific objection per proposal, each "
                    "naming the proposal it is about and pointing at something "
                    "actually present in that code. If a proposal has no real "
                    "weakness from your perspective, say so instead of "
                    "inventing one."
                ),
                model=model,
                options={"temperature": 0.3, "num_predict": 500},
                response_format=self._CRITIQUE_SCHEMA,
                tag=critic.persona_name,
            )))

        if not pending:
            return critiques

        results = engine.run_batch([r for _n, r in pending], use_cache=False)
        for (name, _req), res in zip(pending, results):
            data = self._parse_json(res.content) if res.success else {}
            items = [str(c).strip() for c in (data.get("critiques") or [])]
            critiques[name] = [c for c in items if c][:4]
        return critiques

    # -- phase 3: synthesis -------------------------------------------------

    def debate_and_synthesize(
        self,
        problem: str,
        custom_proposals: Optional[List[CouncilProposal]] = None,
    ) -> CouncilDebateResult:
        """
        Run the council: propose, critique, then pick the winner.

        The consensus code is the winning proposal's own code. It is NOT a
        merge of all three -- the previous version claimed to "combine Clean
        Architecture, Constant-Time Crypto, and In-Memory Caching" while
        emitting a fixed class that did none of it for the given problem.
        Merging three independent designs into one correct program is not
        something this pipeline verifies, so it is not claimed.
        """
        t0 = time.time()
        proposals = custom_proposals or self.generate_proposals(problem)
        critiques = self.critique_proposals(proposals)

        analysed = [p for p in proposals if p.analysed]
        failed = [p.persona_name for p in proposals if not p.analysed]

        if not analysed:
            # Every persona failed. Say so; do not emit code.
            elapsed = round(time.time() - t0, 3)
            return CouncilDebateResult(
                problem_statement=problem,
                proposals=proposals,
                winning_persona="",
                consensus_code="",
                trade_off_analysis=(
                    "No proposal was produced: all three council members "
                    "failed to return a usable analysis, so there is no "
                    "consensus to report."
                ),
                duration_sec=elapsed,
                total_consensus_score=0.0,
                degenerate=True,
                failed_personas=failed,
            )

        best = max(analysed, key=lambda p: (p.overall_score, -analysed.index(p)))
        tied = [p.persona_name for p in analysed
                if p.overall_score == best.overall_score]

        consensus_code = best.proposed_code
        trade_off_analysis = self._render_trade_offs(
            best, analysed, critiques, tied, failed
        )

        elapsed = round(time.time() - t0, 3)
        return CouncilDebateResult(
            problem_statement=problem,
            proposals=proposals,
            winning_persona=best.persona_name,
            consensus_code=consensus_code,
            trade_off_analysis=trade_off_analysis,
            duration_sec=elapsed,
            total_consensus_score=best.overall_score,
            degenerate=False,
            tied=len(tied) > 1,
            tied_personas=tied if len(tied) > 1 else [],
            failed_personas=failed,
        )

    def _render_trade_offs(
        self,
        best: CouncilProposal,
        analysed: List[CouncilProposal],
        critiques: Dict[str, List[str]],
        tied: List[str],
        failed: List[str],
    ) -> str:
        """
        Report the scores the personas actually gave and the critiques they
        actually wrote. The old version asserted every critique had been
        "resolved" in the synthesised code; nothing checked that, and the
        synthesised code was a constant, so it was resolving objections to
        snippets it did not contain.
        """
        lines = ["### Architectural Council Trade-Off Analysis: " + best.persona_name, ""]
        lines.append("Self-reported scores (0-100), by persona:")
        lines.append("")
        lines.append("| Persona | Sec | Perf | Maint | Simp | Overall |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for p in analysed:
            lines.append(
                "| " + p.persona_name
                + " | " + str(p.security_score)
                + " | " + str(p.performance_score)
                + " | " + str(p.maintainability_score)
                + " | " + str(p.simplicity_score)
                + " | **" + str(p.overall_score) + "** |"
            )
        lines.append("")
        lines.append(
            "Scores are each persona's assessment of its own proposal, not an "
            "independent measurement. Nothing here was executed or tested."
        )

        written = {n: c for n, c in critiques.items() if c}
        if written:
            lines.append("")
            lines.append("#### Cross-agent critiques")
            for name, items in written.items():
                lines.append("- **" + name + "**:")
                for c in items:
                    lines.append("  - " + c)
            lines.append("")
            lines.append(
                "These objections are recorded, not resolved -- the consensus "
                "code is the winning proposal as written."
            )

        if len(tied) > 1:
            lines.append("")
            lines.append(
                "> Tie at the top between " + ", ".join(tied) + ". The personas "
                "did not discriminate between these proposals; the winner is "
                "the first in council order, which is a tie-break, not a "
                "judgement."
            )
        if failed:
            lines.append("")
            lines.append(
                "> No analysis returned from: " + ", ".join(failed) +
                ". Scored 0 and excluded from the debate."
            )
        return "\n".join(lines)


# Global instance
agent_council = AgentCouncil()
