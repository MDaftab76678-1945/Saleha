"""
Saleha Core: Swarm Self-Play Arena

Runs a curriculum of coding tasks through a small adversarial loop and
scores each round:

1. CoderAgent generates a candidate solution for the task (real model call).
2. The AST security scanner attacks it; unresolved HIGH findings count as
   attacks that got through.
3. The property fuzzer and the neuro-symbolic invariant scorer rate the
   candidate.
4. Rounds whose candidate failed a check are marked as hard negatives
   (useful later for preference training); the rest are not.

This module does not train anything. It has no adapter weights and performs
no weight averaging -- `RewardAggregator` simply takes the mean of the
top-K round rewards so a run has a single headline number. Training on the
mined hard negatives is a separate, offline step (see the LoRA path), not
something this file claims to do.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from saleha.agents.coder import CoderAgent
from saleha.core.neuro_symbolic_engine import neuro_symbolic_engine
from saleha.core.security_scanner import ASTSecurityScanner
from saleha.core.spics_fuzz_engine import spics_fuzz_engine


@dataclass
class AdversarialBattleResult:
    battle_id: str
    curriculum_level: int
    task_prompt: str
    coder_solution: str
    coder_model_used: str
    coder_succeeded: bool
    security_findings: int
    security_findings_unresolved: int  # HIGH severity, i.e. attacks that got through
    chaos_resilience_pct: float
    fuzz_trials_passed: int
    judge_pareto_reward: float
    hard_negative_mined: bool


@dataclass
class RoundReward:
    round_id: str
    step: int
    reward_score: float  # 0-100, the round's judge_pareto_reward * 100


@dataclass
class SwarmSelfPlaySummary:
    total_battles_fought: int
    curriculum_level_reached: int
    total_attacks_through: int
    hard_negatives_mined_count: int
    rounds_aggregated: int
    aggregate_reward_score: float
    training_duration_sec: float
    run_artifact_path: str


class CurriculumLevelController:
    """Manages 4-tier progressive difficulty curriculum."""

    TIERS = {
        1: ("Elementary Syntax & Type Signatures", 0.70),
        2: ("Memory Safety & Invariant Type Contracts", 0.82),
        3: ("Distributed Concurrency & Consensus Primitives", 0.90),
        4: ("Kernel Zero-Copy & Zero-Day Exploit Defense", 0.95),
    }

    def get_tier_prompts(self, level: int) -> List[str]:
        level = max(1, min(4, level))
        if level == 1:
            return [
                "Implement typed binary search with exact boundary checks",
                "Create balanced parentheses stack validator with O(N) time",
            ]
        elif level == 2:
            return [
                "Design memory-safe LRU cache with RwLock TTL expiration",
                "Implement zero-allocation byte stream circular buffer",
            ]
        elif level == 3:
            return [
                "Synthesize distributed Raft leader election with heartbeats",
                "Build lock-free work-stealing deque with atomic CAS operations",
            ]
        else:
            return [
                "Design kernel-level eBPF packet filter with invariant bounds checking",
                "Implement post-quantum Kyber cryptographic key encapsulation",
            ]


class RewardAggregator:
    """Collects per-round rewards and reports the mean of the top-K.

    This is a scoreboard, not a model operation. There are no weights here.
    """

    def __init__(self, top_k: int = 4):
        self.top_k = max(2, top_k)
        self.rounds: List[RoundReward] = []

    def add_round(self, round_reward: RoundReward) -> None:
        self.rounds.append(round_reward)

    def aggregate(self) -> Dict[str, Any]:
        """Mean reward over the top-K rounds by score."""
        if not self.rounds:
            return {"status": "EMPTY", "aggregate_reward_score": 0.0}

        top = sorted(self.rounds, key=lambda r: r.reward_score, reverse=True)[:self.top_k]
        mean_reward = sum(r.reward_score for r in top) / len(top)
        return {
            "status": "AGGREGATED",
            "rounds_used": [r.round_id for r in top],
            "aggregate_reward_score": round(mean_reward, 2),
        }


class SwarmSelfPlayArena:
    """Multi-agent adversarial self-play scoring arena."""

    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = work_dir or os.path.expanduser("~/.saleha/self_play_arena")
        os.makedirs(self.work_dir, exist_ok=True)
        self.curriculum = CurriculumLevelController()
        self.aggregator = RewardAggregator(top_k=4)
        self._coder = CoderAgent(model="auto")
        self._scanner = ASTSecurityScanner()

    def fight_battle(self, battle_idx: int, level: int, prompt: str) -> AdversarialBattleResult:
        """Runs a single adversarial round for one task prompt."""
        # 1. CoderAgent generates the candidate.
        code_result = self._coder.generate_code(prompt, complexity_score=float(level))
        coder_code = code_result.code
        coder_ok = code_result.success and bool(coder_code.strip())

        if not coder_ok:
            # No candidate to attack or score. Report the round honestly
            # rather than scoring a placeholder.
            return AdversarialBattleResult(
                battle_id=f"battle_{battle_idx:04d}",
                curriculum_level=level,
                task_prompt=prompt,
                coder_solution=coder_code,
                coder_model_used=code_result.model_used,
                coder_succeeded=False,
                security_findings=0,
                security_findings_unresolved=0,
                chaos_resilience_pct=0.0,
                fuzz_trials_passed=0,
                judge_pareto_reward=0.0,
                hard_negative_mined=True,  # a failed generation is a hard negative
            )

        # 2. Security scanner attacks the candidate.
        vulns = self._scanner.scan_code(coder_code, filename="candidate.py")
        findings = len(vulns)
        unresolved = sum(1 for v in vulns if v.severity == "HIGH")

        # 3. Property fuzzing + neuro-symbolic invariant score, on the real code.
        fuzz_res = spics_fuzz_engine.fuzz_test_code(coder_code, function_name="solve", num_trials=50)
        inv_score = neuro_symbolic_engine.score_code(coder_code)

        # 4. Pareto reward: invariant quality, fuzz resilience, and a penalty
        #    for security findings that got through.
        security_factor = 1.0 if unresolved == 0 else max(0.0, 1.0 - 0.25 * unresolved)
        pareto_reward = round(
            (0.4 * inv_score.composite_score)
            + (0.3 * (fuzz_res.invariant_resilience_pct / 100.0))
            + (0.3 * security_factor),
            4,
        )

        # A round is a hard negative if the candidate failed any check.
        is_hard_negative = (
            unresolved > 0
            or fuzz_res.failed_trials > 0
            or inv_score.composite_score < 0.6
        )

        return AdversarialBattleResult(
            battle_id=f"battle_{battle_idx:04d}",
            curriculum_level=level,
            task_prompt=prompt,
            coder_solution=coder_code,
            coder_model_used=code_result.model_used,
            coder_succeeded=True,
            security_findings=findings,
            security_findings_unresolved=unresolved,
            chaos_resilience_pct=fuzz_res.invariant_resilience_pct,
            fuzz_trials_passed=fuzz_res.passed_trials,
            judge_pareto_reward=pareto_reward,
            hard_negative_mined=is_hard_negative,
        )

    def run_arena_training(self, levels_to_run: int = 4) -> SwarmSelfPlaySummary:
        """Runs the curriculum and aggregates the per-round rewards.

        The name is kept for compatibility; no training happens here.
        """
        start_t = time.time()
        battles: List[AdversarialBattleResult] = []
        b_idx = 1

        for lvl in range(1, min(5, levels_to_run + 1)):
            prompts = self.curriculum.get_tier_prompts(lvl)
            for p in prompts:
                battle_res = self.fight_battle(b_idx, lvl, p)
                battles.append(battle_res)
                self.aggregator.add_round(
                    RoundReward(
                        round_id=f"round_lvl_{lvl}_b_{b_idx}",
                        step=b_idx,
                        reward_score=round(battle_res.judge_pareto_reward * 100, 2),
                    )
                )
                b_idx += 1

        aggregate_report = self.aggregator.aggregate()
        run_path = os.path.join(self.work_dir, "self-play-run")
        os.makedirs(run_path, exist_ok=True)
        with open(os.path.join(run_path, "run_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "aggregate": aggregate_report,
                    "battles": [
                        {
                            "battle_id": b.battle_id,
                            "level": b.curriculum_level,
                            "coder_model_used": b.coder_model_used,
                            "coder_succeeded": b.coder_succeeded,
                            "security_findings": b.security_findings,
                            "security_findings_unresolved": b.security_findings_unresolved,
                            "judge_pareto_reward": b.judge_pareto_reward,
                            "hard_negative": b.hard_negative_mined,
                        }
                        for b in battles
                    ],
                },
                f,
                indent=2,
            )

        duration = round(time.time() - start_t, 2)
        total_through = sum(b.security_findings_unresolved for b in battles)
        hard_negatives = sum(1 for b in battles if b.hard_negative_mined)

        return SwarmSelfPlaySummary(
            total_battles_fought=len(battles),
            curriculum_level_reached=min(4, levels_to_run),
            total_attacks_through=total_through,
            hard_negatives_mined_count=hard_negatives,
            rounds_aggregated=len(aggregate_report.get("rounds_used", [])),
            aggregate_reward_score=aggregate_report.get("aggregate_reward_score", 0.0),
            training_duration_sec=duration,
            run_artifact_path=run_path,
        )


swarm_self_play_arena = SwarmSelfPlayArena()
