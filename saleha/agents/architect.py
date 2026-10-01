"""
Saleha Agents: Solution Architect Agent

Deconstructs requirements into production-ready system designs, Architecture Decision
Records (ADR.md), Hexagonal / Clean Architecture boundaries, and API schemas.

What the model writes is checked before it is returned: a named pattern, at
least two components, at least one API contract, and a valid Mermaid
diagram when one is drawn. A design that fails is shown its failures and
asked for once more; `verified` says how it ended.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class ArchitectureDesign:
    goal: str
    adr_title: str
    pattern: str
    components: List[str]
    api_contracts: List[str]
    system_design_md: str
    model_used: str = ""
    # True when no model answered and everything below is the offline
    # template, not a design for this goal.
    from_template: bool = False
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None


_COMPONENT = re.compile(r"(?i)(service|gateway|repository|adapter|controller|broker|worker|api|database|cache|"
                        r"queue|handler|manager)")
_ENDPOINT = re.compile(r"(GET|POST|PUT|PATCH|DELETE)\s+/\S+|endpoint|contract|/api/", re.IGNORECASE)


def _lines(content: str) -> List[str]:
    return [ln.strip(" -*\t") for ln in content.splitlines() if ln.strip().strip("-* \t")]


def design_checks(content: str) -> List[ac.Check]:
    comps = [ln for ln in _lines(content) if _COMPONENT.search(ln)]
    eps = [ln for ln in _lines(content) if _ENDPOINT.search(ln)]
    named = bool(re.search(r"(?i)pattern", content))
    checks = [
        ac.Check("pattern named", ac.PASS if named else ac.FAIL, "" if named else "no architecture pattern named"),
        ac.Check("components", ac.PASS if len(comps) >= 2 else ac.FAIL,
                 f"{len(comps)} component line(s)" + ("" if len(comps) >= 2 else ", need at least 2")),
        ac.Check("API contracts", ac.PASS if eps else ac.FAIL, "" if eps else "no endpoint or contract"),
    ]
    diagrams = [b for info, b in ac.fenced_blocks(content) if info.startswith("mermaid")]
    return checks + [ac.check_mermaid(d) for d in diagrams[:2]]


class ArchitectAgent(BaseAgent):
    """Principal Solution Architect Agent for System Design & ADR Synthesis."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Architect", model=model)

    def design_system(self, goal: str, tech_stack: Optional[str] = None) -> ArchitectureDesign:
        """Designs end-to-end software architecture with ADR specification."""
        stack_str = f"Tech Stack: {tech_stack}\n" if tech_stack else ""
        prompt = f"""You are a Principal Software Architect. Design a production-grade architecture for:
Goal: {goal}
{stack_str}
Output format:
1. Pattern: <name> (e.g. Hexagonal, Event-Driven, Microservices)
2. Components Breakdown (one per line)
3. API Contracts (one per line, e.g. `POST /api/v1/orders - create an order`)
4. A ```mermaid flowchart of the components
5. Full Markdown ADR (Architecture Decision Record)
"""

        def build(content: str) -> Tuple[str, List[ac.Check]]:
            return content, design_checks(content)

        content, checks, resp, _rounds = ac.produce(self, prompt, build)
        from_template = content is None
        if from_template:
            # Labeled DRAFT template: a generic starting scaffold, not an analysis of this goal.
            content = f"""# ADR: {goal}

## Status: DRAFT (offline template -- no model reviewed this goal)
## Architecture Pattern: Hexagonal (Ports & Adapters)
## Key Components:
- API Gateway & Ingress Router
- Domain Core Logic & Aggregate Roots
- Secondary Adapters (PostgreSQL, Redis Cache)
- Event Publisher & Message Broker
"""
        model_lines = [] if from_template else _lines(content)
        comp_like = [ln for ln in model_lines if _COMPONENT.search(ln)]
        ep_like = [ln for ln in model_lines if _ENDPOINT.search(ln)]
        pattern_match = re.search(r"Pattern:\s*([^\n]+)", content, re.IGNORECASE)
        pattern = pattern_match.group(1).strip() if pattern_match else "Hexagonal / Clean Architecture"

        components = comp_like[:8] or [
            "API Ingress & Route Controller",
            "Domain Business Core Entities",
            "Persistence Repository Adapter",
            "Event Telemetry & Metric Publisher"
        ]
        api_contracts = ep_like[:8] or [
            "POST /api/v1/commands - Execute Command Mutation",
            "GET /api/v1/queries - Fetch Read-Optimized Views",
            "GET /health - System Liveness & Readiness Probes"
        ]

        return ArchitectureDesign(
            goal=goal,
            adr_title=f"ADR: {goal}",
            pattern=pattern,
            components=components,
            api_contracts=api_contracts,
            system_design_md=content,
            model_used=resp.model_used,
            from_template=from_template,
            checks=ac.as_dicts(checks),
            verified=None if from_template else ac.verdict(checks),
        )
