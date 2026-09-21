"""
Saleha Core: Multi-Agent Architecture Debate & ADR Synthesis Engine

Conducts structured 3-agent architectural debates (Advocate vs Skeptic vs Principal Judge)
over high-stakes design tradeoffs (e.g. database choice, framework migration, auth protocol),
and synthesizes balanced, industry-standard Architecture Decision Records (ADR.md).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from saleha.agents.base_agent import BaseAgent


@dataclass
class DebateRound:
    round_number: int
    advocate_argument: str
    skeptic_counterargument: str


@dataclass
class ADRDocument:
    title: str
    status: str             # PROPOSED | ACCEPTED | REJECTED | DEPRECATED | UNDECIDED
    context: str
    decision: str
    consequences_positive: List[str] = field(default_factory=list)
    consequences_negative: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    markdown_content: str = ""
    debate_history: List[DebateRound] = field(default_factory=list)
    # False when any of the three agents failed to answer. An ADR whose
    # debate never happened must not read as a decision somebody made:
    # the old fallback emitted "## Status: ACCEPTED" and "Adopt <topic>"
    # after zero model calls.
    model_backed: bool = True
    failure_reason: str = ""


class ArchitectureDebater:
    """Orchestrates multi-agent technical debates and synthesizes Architecture Decision Records."""

    def __init__(self, model: str = "auto") -> None:
        self.model = model
        self.advocate_agent = BaseAgent(role="Innovation & Scalability Advocate", model=model)
        self.skeptic_agent = BaseAgent(role="Risk & SRE Skeptic", model=model)
        self.judge_agent = BaseAgent(role="Principal Enterprise Architect", model=model)

    def debate(self, topic: str, rounds: int = 2, context: str = "") -> ADRDocument:
        """Executes multi-round dialectic debate between Advocate and Skeptic, synthesized by Principal Judge."""
        debate_history: List[DebateRound] = []
        failures: List[str] = []

        advocate_last = ""
        skeptic_last = ""

        for r in range(1, rounds + 1):
            # 1. Advocate Turn
            advocate_prompt = f"""You are the Innovation & Scalability Advocate.
Debate Topic: {topic}
Additional Context: {context or 'Modern high-throughput software architecture'}

Skeptic's Previous Counterargument:
{skeptic_last or '(None - Round 1 Opening Argument)'}

Make your strongest technical argument FOR this architectural choice (performance, developer velocity, scalability). Keep it dense, concrete, and under 300 words."""

            adv_resp = self.advocate_agent.think(advocate_prompt, complexity_score=0.4)
            if adv_resp.success and adv_resp.content.strip():
                advocate_last = adv_resp.content
            else:
                advocate_last = ""
                failures.append(
                    f"round {r} advocate: "
                    f"{getattr(adv_resp, 'error', None) or 'no content returned'}")

            # 2. Skeptic Turn
            skeptic_prompt = f"""You are the Risk & SRE Skeptic.
Debate Topic: {topic}

Advocate's Argument:
{advocate_last}

Critique this proposal rigorously. Highlight operational overhead, failure modes, data consistency risks, lock-in, or maintenance burdens. Keep it dense and under 300 words."""

            skep_resp = self.skeptic_agent.think(skeptic_prompt, complexity_score=0.4)
            if skep_resp.success and skep_resp.content.strip():
                skeptic_last = skep_resp.content
            else:
                skeptic_last = ""
                failures.append(
                    f"round {r} skeptic: "
                    f"{getattr(skep_resp, 'error', None) or 'no content returned'}")

            debate_history.append(DebateRound(
                round_number=r,
                advocate_argument=advocate_last,
                skeptic_counterargument=skeptic_last
            ))

        # 3. Judge Synthesis (ADR Generation)
        judge_prompt = f"""You are the Principal Enterprise Architect.
Synthesize the following debate into an authoritative Architecture Decision Record (ADR).

Topic: {topic}
Context: {context}

Debate Arguments:
"""
        for dr in debate_history:
            judge_prompt += f"\n--- Round {dr.round_number} ---\n[ADVOCATE]:\n{dr.advocate_argument}\n\n[SKEPTIC]:\n{dr.skeptic_counterargument}\n"

        judge_prompt += """
Synthesize a standard ADR format:
# ADR: <Title>
## Status: [ACCEPTED | REJECTED | PROPOSED]
## Context
<Background problem>
## Decision
<Clear definitive decision>
## Positive Consequences
- <pro 1>
- <pro 2>
## Negative Consequences & Risks
- <con 1>
- <con 2>
## Mitigations
- <mitigation 1>
"""
        judge_resp = self.judge_agent.think(judge_prompt, complexity_score=0.5)
        if not (judge_resp.success and judge_resp.content.strip()):
            failures.append(
                "judge: "
                f"{getattr(judge_resp, 'error', None) or 'no content returned'}")

        if failures:
            reason = "; ".join(failures)
            raw_adr = (
                f"# ADR: {topic}\n"
                "## Status: UNDECIDED\n"
                "## Context\n"
                f"{context or topic}\n"
                "## Decision\n"
                "No decision was reached: the debate did not run.\n\n"
                f"Reason: {reason}\n"
            )
            return ADRDocument(
                title=f"ADR: {topic}",
                status="UNDECIDED",
                context=context or topic,
                decision="No decision reached -- the debate did not run.",
                markdown_content=raw_adr,
                debate_history=debate_history,
                model_backed=False,
                failure_reason=reason,
            )

        raw_adr = judge_resp.content
        status_match = re.search(r"##\s*Status:\s*(\w+)", raw_adr, re.IGNORECASE)
        # No status line means the judge did answer but not in the requested
        # shape. That is a parse failure, not an approval -- defaulting to
        # ACCEPTED turned an unreadable reply into a green decision.
        status = status_match.group(1).upper() if status_match else "PROPOSED"

        return ADRDocument(
            title=f"ADR: {topic}",
            status=status,
            context=context or topic,
            decision=self._extract_decision(raw_adr),
            markdown_content=raw_adr.strip(),
            debate_history=debate_history,
            model_backed=True,
        )

    @staticmethod
    def _extract_decision(raw_adr: str) -> str:
        """Pull the judge's actual decision out of the ADR body.

        This field used to be the literal f"Decision reached for: {topic}" --
        the topic echoed back, identical whether the debate concluded for or
        against, so a caller reading `.decision` learned nothing.
        """
        match = re.search(
            r"##\s*Decision\s*\n(.+?)(?=\n##\s|\Z)", raw_adr,
            re.IGNORECASE | re.DOTALL)
        if not match:
            return "Decision section not found in the synthesized ADR."
        body = " ".join(match.group(1).split())
        return body[:400] if body else "Decision section was empty."

    def save_adr(self, adr: ADRDocument, output_dir: str = "docs/adr") -> str:
        """Saves synthesized ADR markdown file to docs/adr directory."""
        os.makedirs(output_dir, exist_ok=True)
        slug = re.sub(r'[^a-zA-Z0-9_-]', '_', adr.title[:40].strip().lower())
        file_path = os.path.join(output_dir, f"{slug}.md")

        tmp_p = f"{file_path}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as f:
            f.write(adr.markdown_content)
        os.replace(tmp_p, file_path)

        return file_path


_debater: Optional[ArchitectureDebater] = None


def get_architecture_debater(model: str = "auto") -> ArchitectureDebater:
    """Lazily built shared instance.

    Constructing this at import time built three BaseAgents for every process
    that merely imported the module, including ones that never debate.
    """
    global _debater
    if _debater is None:
        _debater = ArchitectureDebater(model=model)
    return _debater

