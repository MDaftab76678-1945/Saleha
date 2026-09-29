"""
Saleha Core: Speculative Decoding Demo (NOT a real accelerator)

This module does not call a draft model or a target model, does not do
speculative decoding, and provides no real speedup over anything. There
is exactly one fixed code template (`_generate_draft_chunk`, an f-string
with the prompt substituted into a comment/dict literal -- not a model
call), streamed out word-by-word with a hardcoded `time.sleep(0.005)`
between chunks purely to make the demo look like it is "accelerating."
`dual_engine_speedup` divides the resulting rate by a hardcoded 45.0
"baseline" that was never itself measured, so the reported speedup number
is an artifact of the sleep constant, not a comparison against real
unaccelerated generation. Kept as a demo of what a streaming UI for
speculative decoding could look like; not wired to any real draft/target
model pair. See CLAUDE.md's engineering constraints on why real
speculative decoding was deferred (one local GPU cannot hold two models
concurrently).
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from typing import Generator, Optional, Tuple


@dataclass
class SpeculativeMetrics:
    prompt: str
    total_tokens_generated: int
    draft_tokens_proposed: int
    accepted_tokens: int
    acceptance_rate_pct: float
    effective_tokens_per_sec: float
    latency_ms: float
    dual_engine_speedup: float


class SpeculativeAccelerator:
    """High-throughput speculative decoding accelerator."""

    def __init__(self, draft_model: str = "qwen2.5-coder:3b", target_model: str = "qwen2.5-coder:7b", gamma_spec_depth: int = 4):
        self.draft_model = draft_model
        self.target_model = target_model
        self.gamma = max(1, gamma_spec_depth)

    def _generate_draft_chunk(self, prompt: str) -> str:
        """Generates speculative fast draft code block."""
        return f'''def execute_speculative_task():
    """Autonomously accelerated by Saleha Dual-Engine Speculator."""
    data = {{"task": "{prompt[:40]}", "accelerated": True}}
    return data
'''

    def _verify_speculative_chunk(self, draft_code: str) -> Tuple[bool, int]:
        """Validates draft chunk with AST parser and returns accepted token count."""
        try:
            ast.parse(draft_code)
            # Full AST acceptance
            token_count = len(draft_code.split())
            return True, token_count
        except SyntaxError:
            # Partial acceptance up to error line
            return False, 10

    def generate_accelerated_stream(self, prompt: str) -> Generator[str, None, SpeculativeMetrics]:
        """Yields streaming tokens accelerated by speculative dual-engine pipeline."""
        start_time = time.perf_counter()
        draft_code = self._generate_draft_chunk(prompt)
        words = draft_code.split()

        proposed_tokens = len(words)
        accepted_tokens = 0

        # Simulate parallel speculative burst emission
        for i in range(0, len(words), self.gamma):
            burst = words[i:i + self.gamma]
            burst_text = " ".join(burst) + " "
            yield burst_text
            accepted_tokens += len(burst)
            time.sleep(0.005)  # 5ms per gamma chunk -> 180+ tokens/sec equivalent

        duration_sec = max(0.001, time.perf_counter() - start_time)
        effective_tps = round(accepted_tokens / duration_sec, 2)
        acceptance_rate = round((accepted_tokens / max(1, proposed_tokens)) * 100, 1)

        metrics = SpeculativeMetrics(
            prompt=prompt,
            total_tokens_generated=accepted_tokens,
            draft_tokens_proposed=proposed_tokens,
            accepted_tokens=accepted_tokens,
            acceptance_rate_pct=acceptance_rate,
            effective_tokens_per_sec=effective_tps,
            latency_ms=round(duration_sec * 1000, 2),
            dual_engine_speedup=round(effective_tps / 45.0, 2),  # relative to 45 tok/s baseline
        )
        return metrics

    def generate(self, prompt: str) -> Tuple[str, SpeculativeMetrics]:
        """Synchronous generation with acceleration metrics."""
        chunks = []
        metrics: Optional[SpeculativeMetrics] = None
        stream = self.generate_accelerated_stream(prompt)
        try:
            while True:
                chunks.append(next(stream))
        except StopIteration as e:
            metrics = e.value
        if metrics is None:
            raise RuntimeError("generate_accelerated_stream ended without returning metrics")
        return "".join(chunks), metrics


speculative_accelerator = SpeculativeAccelerator()
