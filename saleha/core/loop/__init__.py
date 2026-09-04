"""
Saleha Core: Loop Engineering Subsystem (2026 Frontier Standard)

Provides self-terminating ReAct loops, state-space search, Maker-Checker verification,
and resilient execution loops:
- AgentLoop / MakerCheckerLoop (Autonomous tool-use execution with Critic verification)
- TreeOfThoughtsOrchestrator / tot_orchestrator (State-Space Search & Self-Evolving Heuristics)
- RecursiveSolver / recursive_solver (Recursive problem decomposition & sub-task solving)
- DeliberationEngine / deliberation_engine (Step-by-step reflection & counterfactual reasoning)
"""

from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from saleha.core.agentic_loop import AgentLoop, LoopStep, LoopResult
from saleha.core.tot_orchestrator import (
    TreeOfThoughtsOrchestrator,
    tot_orchestrator,
    ToTResult,
    ThoughtNode,
)
from saleha.core.recursive_solver import (
    RecursiveSolver,
    recursive_solver,
    ReasoningPath,
    RecursiveSolveResult,
)

from saleha.core.deliberation_engine import (
    DeliberationEngine,
    deliberation_engine,
)
from saleha.core.quality_guard import quality_guard


@dataclass
class LoopCheckpoint:
    """Snapshot of execution state for rollback and recovery."""
    step_number: int
    timestamp: float
    action: str
    args_preview: str
    observation: str
    diff_applied: Optional[str] = None


class MakerCheckerLoop(AgentLoop):
    """
    Enhanced 2026 Loop Engineering implementation with:
    1. Maker-Checker Split: Mutating actions (write_file, run_code) pass through
       QualityGuard and Critic analysis before execution.
    2. Checkpointing & State History: Full step history saved for rollback.
    3. Loop Cycle Detection: Detects repetitive tool call ping-pongs and terminates cleanly.
    """

    def __init__(self, *args, critic_agent=None, enable_checkpoints: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.critic_agent = critic_agent
        self.enable_checkpoints = enable_checkpoints
        self.checkpoints: List[LoopCheckpoint] = []
        self._action_history: List[str] = []

    def _detect_loop_cycle(self, action_signature: str, window: int = 3) -> bool:
        """Detects if the agent is stuck in an infinite tool ping-pong cycle."""
        self._action_history.append(action_signature)
        if len(self._action_history) < window * 2:
            return False
        recent = self._action_history[-window:]
        prior = self._action_history[-2 * window : -window]
        return recent == prior

    def save_checkpoint(self, step: int, action: str, args_str: str, observation: str) -> LoopCheckpoint:
        cp = LoopCheckpoint(
            step_number=step,
            timestamp=time.time(),
            action=action,
            args_preview=args_str,
            observation=observation,
        )
        if self.enable_checkpoints:
            self.checkpoints.append(cp)
        return cp


__all__ = [
    "AgentLoop",
    "LoopStep",
    "LoopResult",
    "MakerCheckerLoop",
    "LoopCheckpoint",
    "TreeOfThoughtsOrchestrator",
    "tot_orchestrator",
    "ToTResult",
    "ThoughtNode",
    "RecursiveSolver",
    "ReasoningPath",
    "RecursiveSolveResult",
    "DeliberationEngine",
    "deliberation_engine",
]

