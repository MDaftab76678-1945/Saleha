"""
Saleha Agents: Solution Architect Agent

Deconstructs requirements into production-ready system designs, Architecture Decision
Records (ADR.md), Hexagonal / Clean Architecture boundaries, and API schemas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.agents.base_agent import BaseAgent, AgentResponse


@dataclass
class ArchitectureDesign:
    goal: str
    adr_title: str
    pattern: str
    components: List[str]
    api_contracts: List[str]
    system_design_md: str
    model_used: str = ""


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

        # Structured default fallback if LLM is offline or in mock mode
        adr_content = resp.content if resp.success and resp.content else f"""# ADR: {goal}

## Status: ACCEPTED
## Architecture Pattern: Hexagonal (Ports & Adapters)
## Key Components:
- API Gateway & Ingress Router
- Domain Core Logic & Aggregate Roots
- Secondary Adapters (PostgreSQL, Redis Cache)
- Event Publisher & Message Broker
"""
        pattern_match = re.search(r"Pattern:\s*([^\n]+)", adr_content, re.IGNORECASE)
        pattern = pattern_match.group(1).strip() if pattern_match else "Hexagonal / Clean Architecture"

        components = [
            "API Ingress & Route Controller",
            "Domain Business Core Entities",
            "Persistence Repository Adapter",
            "Event Telemetry & Metric Publisher"
        ]

        api_contracts = [
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
            model_used=resp.model_used
        )
