"""
Saleha Core: Token Economics & Cloud Cost Analytics Engine

Tracks token usage (prompt, completion, and DeepSeek-R1 reasoning tokens),
computes equivalent cloud API cost savings (vs GPT-4o and Claude 3.5 Sonnet),
and measures local inference latency (tokens/sec, p50, p95).
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

DEFAULT_ANALYTICS_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "token_analytics.json")

# Cloud pricing per 1 Million tokens (USD)
# Reference: Claude 3.5 Sonnet ($3.00 in / $15.00 out), GPT-4o ($2.50 in / $10.00 out)
CLAUDE_SONNET_INPUT_PER_M = 3.00
CLAUDE_SONNET_OUTPUT_PER_M = 15.00
GPT4O_INPUT_PER_M = 2.50
GPT4O_OUTPUT_PER_M = 10.00


@dataclass
class InvocationRecord:
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_sec: float
    tokens_per_sec: float
    cost_saved_usd: float


class TokenAnalyticsEngine:
    """Calculates real-time token economics, local speed benchmarks, and cumulative dollar savings."""

    def __init__(self, storage_path: str = DEFAULT_ANALYTICS_PATH):
        self.storage_path = storage_path
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_reasoning_tokens = 0
        self.total_invocations = 0
        self.total_cost_saved_usd = 0.0
        self.records: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Loads historical analytics from disk."""
        if not os.path.isfile(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
            self.total_prompt_tokens = data.get("total_prompt_tokens", 0)
            self.total_completion_tokens = data.get("total_completion_tokens", 0)
            self.total_reasoning_tokens = data.get("total_reasoning_tokens", 0)
            self.total_invocations = data.get("total_invocations", 0)
            self.total_cost_saved_usd = data.get("total_cost_saved_usd", 0.0)
            self.records = data.get("records", [])[-100:]  # Keep last 100
        except Exception:
            pass

    def _save(self) -> None:
        """Persists analytics to disk atomically."""
        dirname = os.path.dirname(self.storage_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        data = {
            "version": "1.0.0",
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_invocations": self.total_invocations,
            "total_cost_saved_usd": round(self.total_cost_saved_usd, 4),
            "records": self.records[-100:]
        }
        tmp_p = f"{self.storage_path}.tmp.{os.getpid()}"
        try:
            with open(tmp_p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_p, self.storage_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.remove(tmp_p)

    def record_invocation(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        response_time_sec: Optional[float] = None,
        model: str = "local",
        reasoning_tokens: int = 0,
        duration_sec: Optional[float] = None,
    ) -> InvocationRecord:
        """Logs an LLM invocation and updates cumulative token economics."""
        if response_time_sec is None:
            response_time_sec = duration_sec if duration_sec is not None else 0.01

        prompt_tokens = max(0, prompt_tokens)
        completion_tokens = max(0, completion_tokens)
        total_toks = prompt_tokens + completion_tokens
        resp_time = max(0.001, response_time_sec)
        speed = round(completion_tokens / resp_time, 1) if resp_time > 0 else 0.0

        # Cost savings calculation vs Claude 3.5 Sonnet rates
        saved_usd = (
            (prompt_tokens / 1_000_000.0) * CLAUDE_SONNET_INPUT_PER_M +
            (completion_tokens / 1_000_000.0) * CLAUDE_SONNET_OUTPUT_PER_M
        )

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_reasoning_tokens += reasoning_tokens
        self.total_invocations += 1
        self.total_cost_saved_usd += saved_usd

        rec = InvocationRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_toks,
            response_time_sec=round(resp_time, 2),
            tokens_per_sec=speed,
            cost_saved_usd=round(saved_usd, 6)
        )
        self.records.append(asdict(rec))
        self._save()
        return rec

    def get_latency_percentiles(self) -> Dict[str, float]:
        """Calculates p50, p90, and p95 inference speeds (tokens/sec)."""
        if not self.records:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "sample_count": 0.0}
        speeds = sorted([float(r.get("tokens_per_sec", 0.0)) for r in self.records])
        n = len(speeds)

        def _pct(p: float) -> float:
            idx = round((p / 100.0) * (n - 1))
            return round(speeds[max(0, min(n - 1, idx))], 2)

        return {
            "p50": _pct(50.0),
            "p90": _pct(90.0),
            "p95": _pct(95.0),
            "sample_count": float(n),
        }

    def clear(self) -> None:
        """Resets all recorded analytics in memory and on disk."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_reasoning_tokens = 0
        self.total_invocations = 0
        self.total_cost_saved_usd = 0.0
        self.records = []
        self._save()

    def get_summary(self) -> Dict[str, Any]:
        """Returns comprehensive analytics summary."""
        total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        avg_speed = 0.0
        if self.records:
            speeds = [r["tokens_per_sec"] for r in self.records if "tokens_per_sec" in r]
            avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0.0

        percentiles = self.get_latency_percentiles()

        return {
            "total_invocations": self.total_invocations,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_tokens": total_tokens,
            "total_cost_saved_usd": round(self.total_cost_saved_usd, 2),
            "average_speed_tps": avg_speed,
            "latency_percentiles": percentiles,
            "claude_equivalent_saved": f"${round(self.total_cost_saved_usd, 2)} USD",
            "gpt4o_equivalent_saved": f"${round(self.total_cost_saved_usd * 0.75, 2)} USD"
        }


# Global instance
token_analytics = TokenAnalyticsEngine()

