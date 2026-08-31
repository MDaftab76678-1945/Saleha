"""
Saleha Core: Benchmark Score Reporter

Tracks, persists, and visualizes Saleha benchmark scores over time.
Compares against public leaderboard scores for Devin, GPT-4o, SWE-agent.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


DEFAULT_SCORES_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "benchmark_scores.jsonl")

# Public leaderboard scores (SWE-bench Verified, as of 2026)
PUBLIC_LEADERBOARD: Dict[str, float] = {
    "Devin (Cognition)": 13.86,
    "SWE-agent (GPT-4o)": 12.47,
    "AutoCodeRover": 19.00,
    "Agentless (GPT-4o)": 27.33,
    "OpenHands (Claude)": 37.76,
    "Moatless (Claude 3.5)": 38.00,
}


@dataclass
class BenchmarkRun:
    run_id: str
    timestamp: str
    model: str
    suite: str              # "swe_bench" | "humaneval" | "custom"
    total_tasks: int
    solved: int
    score_pct: float
    avg_time_sec: float
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_at_1(self) -> float:
        return self.score_pct


class BenchmarkReporter:
    """Tracks benchmark scores and generates leaderboard comparison reports."""

    def __init__(self, scores_path: str = DEFAULT_SCORES_PATH):
        self.scores_path = scores_path
        os.makedirs(os.path.dirname(scores_path), exist_ok=True)

    def record_run(self, model: str, suite: str, total: int, solved: int,
                   avg_time_sec: float = 0.0, notes: str = "",
                   metadata: Optional[Dict[str, Any]] = None) -> BenchmarkRun:
        """Record a completed benchmark run."""
        import hashlib
        run_id = hashlib.sha256(f"{model}{suite}{time.time()}".encode()).hexdigest()[:12]
        score = round((solved / max(total, 1)) * 100, 2)
        run = BenchmarkRun(
            run_id=run_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            model=model,
            suite=suite,
            total_tasks=total,
            solved=solved,
            score_pct=score,
            avg_time_sec=round(avg_time_sec, 2),
            notes=notes,
            metadata=metadata or {},
        )
        with open(self.scores_path, "a", encoding="utf-8") as f:
            d = run.__dict__.copy()
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        return run

    def load_runs(self, suite: Optional[str] = None) -> List[BenchmarkRun]:
        """Load all recorded benchmark runs."""
        runs = []
        if not os.path.exists(self.scores_path):
            return runs
        with open(self.scores_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if suite and data.get("suite") != suite:
                        continue
                    meta = data.pop("metadata", {})
                    run = BenchmarkRun(**data, metadata=meta)
                    runs.append(run)
                except Exception:
                    continue
        return runs

    def best_score(self, suite: str = "swe_bench") -> Optional[float]:
        """Return the best score ever achieved on a suite."""
        runs = self.load_runs(suite=suite)
        if not runs:
            return None
        return max(r.score_pct for r in runs)

    def generate_leaderboard_report(self, saleha_score: Optional[float] = None) -> str:
        """Generate a text leaderboard comparison report."""
        best = saleha_score or self.best_score() or 0.0
        lines = [
            "\n🏆 SWE-bench Verified Leaderboard\n" + "="*45,
            f"  {'Tool':<30} {'Score':>8}",
            "  " + "-"*40,
        ]
        all_entries = dict(PUBLIC_LEADERBOARD)
        all_entries["🤖 Saleha AI (local, $0)"] = best
        for name, score in sorted(all_entries.items(), key=lambda x: -x[1]):
            marker = " ← YOU" if "Saleha" in name else ""
            lines.append(f"  {name:<30} {score:>6.2f}%{marker}")
        lines.append("="*45)
        return "\n".join(lines)

    def generate_badge_markdown(self, suite: str = "swe_bench") -> str:
        """Generate a README badge for best benchmark score."""
        best = self.best_score(suite=suite)
        if best is None:
            return "![SWE-bench](https://img.shields.io/badge/SWE--bench-Not%20Run-lightgrey.svg)"
        color = "brightgreen" if best >= 20 else "yellow" if best >= 10 else "red"
        score_str = f"{best:.1f}%25"
        label = f"SWE--bench%20{suite.replace('_', '--')}"
        return f"![SWE-bench](https://img.shields.io/badge/{label}-{score_str}-{color}.svg)"


# Global instance
benchmark_reporter = BenchmarkReporter()
