"""
Saleha Batched Mutation Fuzzing Engine.

This does NOT do distributed peer-to-peer computation. A prior version of
this module claimed "Libp2p-inspired Peer Discovery", real network peers
at hardcoded fake IPs (192.168.1.11-14), and "Consensus Aggregation over
Asynchronous Gossip" -- none of that exists. There is no network protocol,
no peer discovery, no inter-process or inter-machine communication
anywhere in this file. It also returned `consensus_achieved=True`
unconditionally and counted "crashes" via a naive substring check
(`"eval(" in code or "/ 0" in code`) that never actually ran the code.

What this module does for real: splits a fuzzing budget into batches
(labelled "workers", since they are just partitions of one local run, not
separate machines) and runs the real property-based fuzzer
(SPICSFuzzEngine, the same real fuzz engine swarm_self_play_arena.py and
grpo_reasoning_trainer.py use) against each batch, aggregating genuine
pass/fail counts. No fake peer nodes, no fake network addresses, no
unconditional consensus claim.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

from saleha.core.spics_fuzz_engine import spics_fuzz_engine


@dataclass
class BatchResult:
    batch_id: int
    trials_run: int
    trials_passed: int
    trials_failed: int


@dataclass
class BatchedFuzzResult:
    task_id: str
    total_trials_requested: int
    total_trials_run: int
    batches_run: int
    trials_passed: int
    trials_failed: int
    resilience_pct: float
    duration_ms: float
    batches: List[BatchResult] = field(default_factory=list)


class BatchedFuzzingEngine:
    """Splits a fuzz budget into batches and runs the real SPICS fuzzer
    against each, aggregating genuine results. Single-process; does not
    distribute work across machines or processes."""

    def distribute_mutation_fuzzing(
        self, code: str, total_mutations: int = 1000, num_batches: int = 4, function_name: str = "solve"
    ) -> BatchedFuzzResult:
        num_batches = max(1, num_batches)
        per_batch = max(1, total_mutations // num_batches)

        t0 = time.perf_counter()
        batches: List[BatchResult] = []
        total_passed = 0
        total_failed = 0
        total_run = 0

        for b in range(num_batches):
            fuzz_res = spics_fuzz_engine.fuzz_test_code(code, function_name=function_name, num_trials=per_batch)
            batches.append(
                BatchResult(
                    batch_id=b,
                    trials_run=fuzz_res.total_fuzz_trials,
                    trials_passed=fuzz_res.passed_trials,
                    trials_failed=fuzz_res.failed_trials,
                )
            )
            total_run += fuzz_res.total_fuzz_trials
            total_passed += fuzz_res.passed_trials
            total_failed += fuzz_res.failed_trials

        duration_ms = (time.perf_counter() - t0) * 1000
        resilience = round((total_passed / total_run) * 100, 2) if total_run else 0.0

        return BatchedFuzzResult(
            task_id=f"fuzz_{int(t0 * 1000) % 100000}",
            total_trials_requested=total_mutations,
            total_trials_run=total_run,
            batches_run=num_batches,
            trials_passed=total_passed,
            trials_failed=total_failed,
            resilience_pct=resilience,
            duration_ms=round(duration_ms, 2),
            batches=batches,
        )


batched_fuzzing_engine = BatchedFuzzingEngine()
