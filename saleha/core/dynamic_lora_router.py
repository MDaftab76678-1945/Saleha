"""
Saleha Core: keyword-based domain classifier for task prompts.

HONEST SCOPE NOTE. This loads no LoRA adapter, swaps no weights, and fuses
nothing. It is a keyword matcher over the prompt string, and the `rank_r` /
`alpha` fields below are metadata describing adapters that would have to be
trained first -- no file named by any `adapter_id` exists in this repository
(checked).

It previously called itself a "Dynamic Hot-Swappable Micro-LoRA Router"
claiming "sub-5ms dynamic adapter switching" and "Multi-Adapter Dynamic
Weight Fusion (alpha_1 * LoRA_A + alpha_2 * LoRA_B)". The "sub-5ms switch"
was the cost of setting a boolean on six dicts, and `confidence` was the
literal 0.96 on every call -- returned with equal confidence for a prompt it
classified by a real keyword hit and for one it fell through to "general" on,
which is precisely backwards.

`confidence` is now the share of the prompt's matched keywords that belong to
the winning domain, and a fall-through to "general" reports 0.0 -- an honest
"no signal", not 0.96.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class MicroAdapterSpec:
    adapter_id: str
    domain: str
    rank_r: int
    alpha: int
    description: str
    active: bool = False
    load_latency_ms: float = 0.0


@dataclass
class LoRARoutingDecision:
    task_prompt: str
    detected_domain: str
    selected_adapter: str
    classification_ms: float
    # Share of matched domain keywords belonging to the winning domain, in
    # [0.0, 1.0]. 0.0 means no keyword matched and "general" was the
    # fall-through, not a positive identification.
    confidence: float
    matched_keywords: List[str]
    # No adapter is loaded by this class. True would require a trained
    # adapter file, and none exists in this repository.
    adapter_loaded: bool = False


# Domain keywords, checked in order. First domain with a match wins, matching
# the original precedence.
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "frontend": ["react", "frontend", "ui", "css", "component", "button", "html"],
    "security": ["security", "cwe", "owasp", "jwt", "auth", "inject", "encrypt"],
    "database": ["postgres", "sql", "db", "database", "redis", "schema", "table"],
    "algorithms": ["algorithm", "mcts", "tree", "graph", "dp", "sort", "binary"],
    "backend": ["fastapi", "api", "backend", "endpoint", "route", "async"],
}


class DynamicLoRARouter:
    """Classifies a prompt into a domain by keyword match. Loads nothing."""

    def __init__(self):
        self.adapters: Dict[str, MicroAdapterSpec] = {
            "backend": MicroAdapterSpec("lora_backend_v3", "backend", rank_r=16, alpha=32, description="FastAPI, AsyncIO, Microservices"),
            "frontend": MicroAdapterSpec("lora_frontend_v3", "frontend", rank_r=16, alpha=32, description="React 19, Next.js 15, Vanilla CSS"),
            "security": MicroAdapterSpec("lora_security_v3", "security", rank_r=32, alpha=64, description="OWASP SAST, Cryptography, 0-CWE"),
            "algorithms": MicroAdapterSpec("lora_algorithms_v3", "algorithms", rank_r=16, alpha=32, description="MCTS, Dynamic Programming, Graphs"),
            "database": MicroAdapterSpec("lora_database_v3", "database", rank_r=16, alpha=32, description="PostgreSQL, Redis, Invariant Schemas"),
            "general": MicroAdapterSpec("lora_general_v3", "general", rank_r=8, alpha=16, description="General Polyglot Coding & Docs"),
        }
        self.active_adapter = "general"
        self.adapters["general"].active = True

    def route_and_switch(self, task_prompt: str) -> LoRARoutingDecision:
        """Classifies `task_prompt` into a domain by keyword match.

        `confidence` is the winning domain's share of all matched keywords, so
        a prompt hitting only frontend terms scores 1.0 while one straddling
        two domains scores proportionally lower. A prompt matching nothing
        falls through to "general" with confidence 0.0 -- the old code
        returned the literal 0.96 for that case too, reporting a fall-through
        with the same confidence as a clean hit.
        """
        start_t = time.perf_counter()
        prompt_lower = task_prompt.lower()

        hits: Dict[str, List[str]] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            matched = [k for k in keywords if k in prompt_lower]
            if matched:
                hits[domain] = matched

        if hits:
            target_domain = next(d for d in DOMAIN_KEYWORDS if d in hits)
            total_matches = sum(len(m) for m in hits.values())
            confidence = round(len(hits[target_domain]) / total_matches, 2)
            matched_keywords = hits[target_domain]
        else:
            target_domain = "general"
            confidence = 0.0
            matched_keywords = []

        for name, spec in self.adapters.items():
            spec.active = (name == target_domain)
        self.active_adapter = target_domain

        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)

        return LoRARoutingDecision(
            task_prompt=task_prompt,
            detected_domain=target_domain,
            selected_adapter=self.adapters[target_domain].adapter_id,
            classification_ms=duration_ms,
            confidence=confidence,
            matched_keywords=matched_keywords,
            adapter_loaded=False,
        )

    def get_adapter_inventory(self) -> List[MicroAdapterSpec]:
        """Returns all registered domain micro-adapters."""
        return list(self.adapters.values())


dynamic_lora_router = DynamicLoRARouter()
