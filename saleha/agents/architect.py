"""
Saleha Agents: Solution Architect Agent

Deconstructs requirements into production-ready system designs, Architecture Decision
Records (ADR.md), Hexagonal / Clean Architecture boundaries, and API schemas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from saleha.agents.base_agent import AgentResponse, BaseAgent


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
1. Pattern (e.g. Hexagonal, Event-Driven, Microservices)
2. Components Breakdown
3. API Contracts (Endpoints/Protocols)
4. Full Markdown ADR (Architecture Decision Record)
"""
        resp: AgentResponse = self.think(prompt)

        if resp.success and resp.content and resp.content.strip():
            # Components and contracts come from the model's answer: the
            # lines it presents as components/endpoints, not a fixed list.
            # Falls back to the template below when parsing finds nothing.
            model_lines = [ln.strip(" -*\t") for ln in resp.content.splitlines()
                           if ln.strip().strip("-* \t")]
            comp_like = [ln for ln in model_lines
                         if re.search(r"(?i)(service|gateway|repository|adapter|controller|broker|worker|api|database|cache|queue|handler|manager)", ln)]
            ep_like = [ln for ln in model_lines
                       if re.search(r"(GET|POST|PUT|PATCH|DELETE)\s+/\S+|endpoint|contract|/api/", ln, re.IGNORECASE)]
            adr_content = resp.content
            from_template = False
        else:
            comp_like, ep_like, adr_content = [], [], ""
            from_template = True

        # Structured default fallback if LLM is offline or in mock mode.
        # Labeled DRAFT template: the components below are a generic
        # starting scaffold, not an analysis of this goal.
        if from_template:
            adr_content = f"""# ADR: {goal}

## Status: DRAFT (offline template -- no model reviewed this goal)
## Architecture Pattern: Hexagonal (Ports & Adapters)
## Key Components:
- API Gateway & Ingress Router
- Domain Core Logic & Aggregate Roots
- Secondary Adapters (PostgreSQL, Redis Cache)
- Event Publisher & Message Broker
"""
        pattern_match = re.search(r"Pattern:\s*([^\n]+)", adr_content, re.IGNORECASE)
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
            system_design_md=adr_content,
            model_used=resp.model_used,
            from_template=from_template,
        )
