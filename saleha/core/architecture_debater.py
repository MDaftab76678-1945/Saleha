"""
Saleha Core: Multi-Agent Architecture Debate & ADR Synthesis Engine

Conducts structured 3-agent architectural debates (Advocate vs Skeptic vs Principal Judge)
over high-stakes design tradeoffs (e.g. database choice, framework migration, auth protocol),
and synthesizes balanced, industry-standard Architecture Decision Records (ADR.md).
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from saleha.agents.base_agent import BaseAgent


@dataclass
class DebateRound:
    round_number: int
    advocate_argument: str
    skeptic_counterargument: str


@dataclass
class ADRDocument:
    title: str
    status: str             # PROPOSED | ACCEPTED | REJECTED | DEPRECATED
    context: str
    decision: str
    consequences_positive: List[str] = field(default_factory=list)
    consequences_negative: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    markdown_content: str = ""
    debate_history: List[DebateRound] = field(default_factory=list)


class ArchitectureDebater:
    """Orchestrates multi-agent technical debates and synthesizes Architecture Decision Records."""

    def __init__(self, model: str = "auto"):
        self.model = model
        self.advocate_agent = BaseAgent(role="Innovation & Scalability Advocate", model=model)
        self.skeptic_agent = BaseAgent(role="Risk & SRE Skeptic", model=model)
        self.judge_agent = BaseAgent(role="Principal Enterprise Architect", model=model)

    def debate(self, topic: str, rounds: int = 2, context: str = "") -> ADRDocument:
        """Executes multi-round dialectic debate between Advocate and Skeptic, synthesized by Principal Judge."""
        debate_history: List[DebateRound] = []

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
            advocate_last = adv_resp.content if adv_resp.success else f"Advocate argument for {topic}."

            # 2. Skeptic Turn
            skeptic_prompt = f"""You are the Risk & SRE Skeptic.
Debate Topic: {topic}

Advocate's Argument:
{advocate_last}

Critique this proposal rigorously. Highlight operational overhead, failure modes, data consistency risks, lock-in, or maintenance burdens. Keep it dense and under 300 words."""

            skep_resp = self.skeptic_agent.think(skeptic_prompt, complexity_score=0.4)
            skeptic_last = skep_resp.content if skep_resp.success else f"Skeptic counterargument for {topic}."

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
        raw_adr = judge_resp.content if judge_resp.success else f"# ADR: {topic}\n## Status: ACCEPTED\n## Decision\nAdopt {topic} with monitoring."

        status_match = re.search(r"## Status:\s*(\w+)", raw_adr, re.IGNORECASE)
        status = status_match.group(1).upper() if status_match else "ACCEPTED"

        return ADRDocument(
            title=f"ADR: {topic}",
            status=status,
            context=context or topic,
            decision=f"Decision reached for: {topic}",
            markdown_content=raw_adr.strip(),
            debate_history=debate_history
        )

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


# Global instance
architecture_debater = ArchitectureDebater()

