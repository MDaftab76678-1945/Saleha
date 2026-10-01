"""ChaosResilienceAgent: circuit-breaker template for a named service.

What this is, stated plainly because it used to claim much more: it does not
inject faults and does not run an experiment. `run_chaos_test` used to return
a fixed `resilience_score_pct=99.98`, a fixed "cascade thread exhaustion
occurs in 1.2s" analysis and a "Simulated 500ms Socket Timeout" scenario for
any target at all -- numbers no code ever measured, surfaced by the octopus
SRE arm, `/chaos` in chat and the web API.

It now returns the same circuit-breaker template (a real, usable decorator)
with `measured=False` and no score for the service -- and the template
itself is put through injected faults each time (`verify_breaker`): it must
pass the first failures through, open and fast-fail without calling the
service, half-open after its timeout and close on success. For an actual
probe of a callable, see `saleha.core.devops.chaos_engine`.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from saleha.agents.artifact_check import FAIL, PASS, Check, run_python
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
    """Output of `run_chaos_test`. `measured` is False: nothing was injected into the service."""
    target_service: str
    injected_fault_scenario: str
    system_impact_analysis: str
    circuit_breaker_patch: str
    resilience_score_pct: Optional[float]  # None: not measured
    experiment_duration_ms: float
    measured: bool = False
    # The template itself, put through injected faults: does it open, fast-fail,
    # half-open and close as it says? Measured on the template, not on the service.
    breaker_checks: List[Dict[str, str]] = field(default_factory=list)
    breaker_verified: Optional[bool] = None


_PROBE = """

import json as _json
import time as _time
_calls = {"n": 0, "fail": True}


@resilient_circuit_breaker(max_failures=3, reset_timeout_sec=%(reset)s)
def _flaky():
    _calls["n"] += 1
    if _calls["fail"]:
        raise ConnectionError("injected fault")
    return "ok"


def _outcome():
    try:
        return _flaky()
    except CircuitBreakerOpenException:
        return "fast-fail"
    except ConnectionError:
        return "fault"


_first = [_outcome() for _ in range(3)]
_before = _calls["n"]
_open = _outcome()
_extra = _calls["n"] - _before
_time.sleep(%(reset)s * 2)
_calls["fail"] = False
_after = _outcome()
_calls["fail"] = True
_again = _outcome()
print("@@" + _json.dumps({"first": _first, "open": _open, "extra": _extra, "after": _after, "again": _again}))
"""


def verify_breaker(template: str = CIRCUIT_BREAKER_TEMPLATE, reset: float = 0.05) -> List[Check]:
    """Inject failures into a function wrapped by the template, in a throwaway process, and watch its states."""
    ran, out = run_python(template + _PROBE % {"reset": reset}, timeout=30, name="template runs", screen=False)
    if "@@" not in out:
        return [ran if ran.status != PASS else Check("template runs", FAIL, "no result came back")]
    r: Dict[str, Any] = json.loads(out.split("@@", 1)[1].splitlines()[0])
    return [
        Check("passes the first 3 faults through", PASS if r["first"] == ["fault"] * 3 else FAIL, str(r["first"])),
        Check("opens and fast-fails without calling the service",
              PASS if r["open"] == "fast-fail" and r["extra"] == 0 else FAIL,
              f"4th call: {r['open']}, service called {r['extra']} more time(s)"),
        Check("half-opens after the timeout and closes on success", PASS if r["after"] == "ok" else FAIL,
              f"call after {reset * 2:.2f}s: {r['after']}"),
        Check("counts failures from zero once closed", PASS if r["again"] == "fault" else FAIL,
              f"next fault: {r['again']}"),
    ]


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
            f"Resilience score: {NOT_MEASURED}\n"
            f"The template under injected faults: "
            f"{'opens, fast-fails, half-opens and closes as it should' if result.breaker_verified else 'FAILED'}"
            f" ({sum(c['status'] == PASS for c in result.breaker_checks)}/{len(result.breaker_checks)} checks)\n\n"
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
        """The circuit-breaker template, its behaviour checked under injected faults.

        No fault is injected into `target_service` and nothing about it is scored.
        """
        start = time.perf_counter()
        checks = verify_breaker()
        duration_ms = (time.perf_counter() - start) * 1000
        return ChaosExperimentResult(
            breaker_checks=[asdict(c) for c in checks],
            breaker_verified=all(c.status == PASS for c in checks),
            target_service=target_service,
            injected_fault_scenario="none (this agent does not inject faults)",
            system_impact_analysis=NOT_MEASURED,
            circuit_breaker_patch=CIRCUIT_BREAKER_TEMPLATE,
            resilience_score_pct=None,
            experiment_duration_ms=round(duration_ms, 2),
            measured=False,
        )


chaos_resilience = ChaosResilienceAgent()
