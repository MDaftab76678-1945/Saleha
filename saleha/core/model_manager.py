"""
Saleha Core: Model Manager & Local Inference Profiler

Handles downloading, verifying, and benchmarking recommended Ollama models
for fast speculative routing and deep reasoning swarms.
"""

from __future__ import annotations

import time
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from saleha.agents.base_agent import BaseAgent


RECOMMENDED_MODELS = {
    "fast": "qwen2.5-coder:1.5b",
    "reasoning": "deepseek-r1:8b",
    "flagship": "qwen2.5-coder:7b"
}


@dataclass
class BenchmarkResult:
    model_name: str
    tokens_generated: int
    duration_sec: float
    tokens_per_sec: float
    success: bool = True
    error: str = ""


class ModelManager:
    """Manages Ollama model lifecycle, pulling, and speed benchmarks."""

    def pull_model(self, model_name: str) -> Tuple[bool, str]:
        """Pulls an Ollama model using local CLI."""
        try:
            res = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return True, f"Successfully pulled {model_name}"
            return False, res.stderr.strip() or f"Failed to pull {model_name}"
        except FileNotFoundError:
            return False, "Ollama CLI not found on PATH. Please install Ollama from https://ollama.ai"

    def benchmark_model(self, model_name: str = "qwen2.5-coder:1.5b") -> BenchmarkResult:
        """Executes a standardized code generation benchmark to measure inference speed."""
        agent = BaseAgent(role="Speed Benchmarker", model=model_name)
        start_t = time.time()

        prompt = "Write a fast Python function to compute the Fibonacci sequence up to n numbers. Keep it concise."
        resp = agent.think(prompt, complexity_score=0.2)
        elapsed = max(0.001, time.time() - start_t)

        if not resp.success or not resp.content:
            return BenchmarkResult(
                model_name=model_name,
                tokens_generated=0,
                duration_sec=round(elapsed, 2),
                tokens_per_sec=0.0,
                success=False,
                error="Model invocation failed during benchmark."
            )

        # Estimate tokens (~4 chars/token)
        tokens_est = max(10, len(resp.content) // 4)
        speed = round(tokens_est / elapsed, 1)

        return BenchmarkResult(
            model_name=model_name,
            tokens_generated=tokens_est,
            duration_sec=round(elapsed, 2),
            tokens_per_sec=speed,
            success=True
        )


# Global instance
model_manager = ModelManager()
