"""
Saleha Core: Benchmark Score Reporter

Tracks and persists Saleha's own benchmark runs over time.

It used to render Saleha's score into a single ranked table beside published
SWE-bench Verified figures for Devin, OpenHands and others, marking our row
" <- YOU". That comparison was never valid: those figures are Pass@1 on
SWE-bench Verified (real multi-file repository issues, scored by the official
Docker harness), and this project has never run that benchmark -- its own
numbers come from twelve small self-contained problems
(`real_task_bench.py`). Putting the two in one sorted column implied a rank
across a benchmark we have not run, which is how `swe-export` ended up
publishing a fabricated 100.00% directly above Devin's real 13.86%.

The published figures are kept as reference context, clearly labelled as a
different benchmark, and are never sorted against our own score.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


DEFAULT_SCORES_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "benchmark_scores.jsonl")

# Published Pass@1 figures for other tools on **SWE-bench Verified**, as
# reported by their authors. Reference context only. Saleha has not run
# SWE-bench Verified, so none of these is comparable to a Saleha score --
# see `real_task_bench.scored_swebench_availability()` for what is missing.
PUBLIC_SWEBENCH_VERIFIED_REFERENCE: Dict[str, float] = {
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

    def best_score(self, suite: str = "local_tasks") -> Optional[float]:
        """Return the best score ever achieved on a suite."""
        runs = self.load_runs(suite=suite)
        if not runs:
            return None
        return max(r.score_pct for r in runs)

    def generate_leaderboard_report(self, saleha_score: Optional[float] = None) -> str:
        """Report Saleha's own best local score, then the published SWE-bench
        figures as clearly separated reference context.

        The two are never merged into one sorted ranking: they are different
        benchmarks, and sorting them together asserts a comparison this
        project has not earned.
        """
        best = saleha_score if saleha_score is not None else self.best_score()
        lines = ["\nSaleha local task benchmark (real_task_bench.py)",
                 "=" * 58]
        if best is None:
            lines.append("  No run recorded yet. Run `saleha benchmark-local` first.")
        else:
            lines.append(f"  Best recorded local pass rate: {best:.2f}%")
        lines += [
            "  Twelve small self-contained problems on one machine.",
            "",
            "For reference -- published Pass@1 on SWE-bench Verified,",
            "a different and much harder benchmark Saleha has NOT run:",
            "-" * 58,
        ]
        for name, score in sorted(PUBLIC_SWEBENCH_VERIFIED_REFERENCE.items(),
                                  key=lambda x: -x[1]):
            lines.append(f"  {name:<30} {score:>6.2f}%")
        lines += [
            "-" * 58,
            "  These are not comparable to the number above.",
            "=" * 58,
        ]
        return "\n".join(lines)

    def generate_badge_markdown(self, suite: str = "local_tasks") -> str:
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

