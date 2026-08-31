"""
Saleha Core: Autonomous Chaos Engineering & Fault Injection Engine

Injects controlled chaos, network delays, synthetic exceptions, and payload corruptions
into test suites and function executions to evaluate and verify production fault-tolerance.
"""

from __future__ import annotations

import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any


@dataclass
class ChaosFaultConfig:
    inject_latency_ms: int = 0
    failure_rate: float = 0.0          # 0.0 to 1.0 probability of raising exception
    corrupt_payload: bool = False
    simulate_timeout: bool = False
    exception_type: str = "RuntimeError"
    exception_message: str = "Injected Chaos Fault: Simulated Connection Drop"


@dataclass
class ChaosProbeResult:
    total_iterations: int
    successful_executions: int
    injected_faults: int
    handled_cleanly: int
    unhandled_crashes: int
    resilience_score: float             # 0.0 to 1.0 (1.0 = perfect resilience)
    fault_logs: List[str] = field(default_factory=list)


class ChaosEngine:
    """Probes system resilience through randomized synthetic fault injections."""

    def __init__(self):
        self.active_experiments: Dict[str, ChaosFaultConfig] = {}

    def wrap_execution(self, func: Callable, *args, config: Optional[ChaosFaultConfig] = None, **kwargs) -> Any:
        """Executes a callable under an active chaos injection configuration."""
        cfg = config or ChaosFaultConfig()

        # 1. Latency injection
        if cfg.inject_latency_ms > 0:
            time.sleep(cfg.inject_latency_ms / 1000.0)

        # 2. Timeout injection
        if cfg.simulate_timeout:
            raise TimeoutError("Injected Chaos Fault: Network Socket Timeout")

        # 3. Random exception injection
        if cfg.failure_rate > 0 and random.random() < cfg.failure_rate:
            raise RuntimeError(cfg.exception_message)

        # 4. Payload corruption if requested
        if cfg.corrupt_payload and args:
            corrupted_args = list(args)
            corrupted_args[0] = None  # Inject unexpected None
            return func(*corrupted_args, **kwargs)

        return func(*args, **kwargs)

    def probe_resilience(
        self,
        target_callable: Callable,
        iterations: int = 20,
        config: Optional[ChaosFaultConfig] = None
    ) -> ChaosProbeResult:
        """Runs target_callable repeatedly under chaos conditions to calculate a Resilience Score."""
        cfg = config or ChaosFaultConfig(failure_rate=0.3, inject_latency_ms=1)
        successes = 0
        injected = 0
        handled = 0
        crashes = 0
        logs = []

        for i in range(1, iterations + 1):
            try:
                self.wrap_execution(target_callable, config=cfg)
                successes += 1
            except (RuntimeError, TimeoutError) as e:
                injected += 1
                handled += 1
                logs.append(f"Iteration {i}: Handled synthetic fault - {e}")
            except Exception as e:
                injected += 1
                crashes += 1
                logs.append(f"Iteration {i}: Unhandled crash - {type(e).__name__}: {e}")

        total_faults = injected if injected > 0 else 1
        resilience = round(handled / total_faults, 2)

        return ChaosProbeResult(
            total_iterations=iterations,
            successful_executions=successes,
            injected_faults=injected,
            handled_cleanly=handled,
            unhandled_crashes=crashes,
            resilience_score=resilience,
            fault_logs=logs
        )


# Global instance
chaos_engine = ChaosEngine()
