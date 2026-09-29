"""ChaosResilienceAgent: circuit-breaker template for a named service.

What this is, stated plainly because it used to claim much more: it does not
inject faults and does not run an experiment. `run_chaos_test` used to return
a fixed `resilience_score_pct=99.98`, a fixed "cascade thread exhaustion
occurs in 1.2s" analysis and a "Simulated 500ms Socket Timeout" scenario for
any target at all -- numbers no code ever measured, surfaced by the octopus
SRE arm, `/chaos` in chat and the web API.

It now returns the same circuit-breaker template (a real, usable decorator)
with `measured=False` and no score. For an actual probe of a callable, see
`saleha.core.devops.chaos_engine`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from saleha.agents.base_agent import AgentResponse, BaseAgent

NOT_MEASURED = "not measured -- no fault was injected"

CIRCUIT_BREAKER_TEMPLATE = """import time
import functools

class CircuitBreakerOpenException(Exception):
    pass

def resilient_circuit_breaker(max_failures: int = 3, reset_timeout_sec: float = 5.0):
    \"\"\"Circuit breaker: opens after max_failures, half-opens after reset_timeout_sec.\"\"\"
    def decorator(func):
        failures = 0
        last_failure_time = 0.0
        state = "CLOSED"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal failures, last_failure_time, state
            if state == "OPEN":
                if time.time() - last_failure_time > reset_timeout_sec:
                    state = "HALF_OPEN"
                else:
                    raise CircuitBreakerOpenException("Circuit is OPEN. Fast-failing downstream request.")
            try:
                result = func(*args, **kwargs)
                if state == "HALF_OPEN":
                    state = "CLOSED"
                    failures = 0
                return result
            except Exception as e:
                failures += 1
                last_failure_time = time.time()
                if failures >= max_failures:
                    state = "OPEN"
                raise e
        return wrapper
    return decorator"""


@dataclass
class ChaosExperimentResult:
    """Output of `run_chaos_test`. `measured` is False: nothing was injected."""
    target_service: str
    injected_fault_scenario: str
    system_impact_analysis: str
    circuit_breaker_patch: str
    resilience_score_pct: Optional[float]  # None: not measured
    experiment_duration_ms: float
    measured: bool = False


class ChaosResilienceAgent(BaseAgent):
    """Returns a circuit-breaker template for a service; runs no experiment."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Chaos & Resilience Architect", model=model)
        self.name = "ChaosResilienceAgent"

    def execute(self, prompt: str, **kwargs) -> AgentResponse:
        start = time.perf_counter()
        result = self.run_chaos_test(prompt)
        duration = time.perf_counter() - start

        content = (
            f"[ChaosResilienceAgent] Circuit-breaker template for: \"{result.target_service}\"\n\n"
            f"Fault injection: {result.injected_fault_scenario}\n"
            f"Resilience score: {NOT_MEASURED}\n\n"
            f"Circuit breaker template (not tested against this service):\n"
            f"```python\n{result.circuit_breaker_patch}\n```"
        )

        return AgentResponse(
            success=True,
            content=content,
            model_used="template",
            response_time=duration,
            tokens_used=len(content.split()) * 2,
        )

    def run_chaos_test(self, target_service: str) -> ChaosExperimentResult:
        """Return the circuit-breaker template. No fault is injected; nothing is scored."""
        start = time.perf_counter()
        duration_ms = (time.perf_counter() - start) * 1000
        return ChaosExperimentResult(
            target_service=target_service,
            injected_fault_scenario="none (this agent does not inject faults)",
            system_impact_analysis=NOT_MEASURED,
            circuit_breaker_patch=CIRCUIT_BREAKER_TEMPLATE,
            resilience_score_pct=None,
            experiment_duration_ms=round(duration_ms, 2),
            measured=False,
        )


chaos_resilience = ChaosResilienceAgent()
