"""
Saleha Core: Structured Metrics (B3 -- Observability)

Pehle koi telemetry hi nahi thi (purani telemetry.py dead-code ban gayi thi).
Ab har orchestrator run ka outcome append-only JSONL mein persist hota hai:

    ~/.saleha/metrics.jsonl

Har line: {"ts": ..., "event": "run_completed", "success": true, "attempts": 2,
"model": "...", "duration_sec": 12.3, ...}

`saleha metrics` CLI iska summary dikhata hai (success rate, avg attempts,
per-model breakdown, recent events).
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class MetricsTracker:
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            saleha_dir = os.path.join(os.path.expanduser("~"), ".saleha")
            os.makedirs(saleha_dir, exist_ok=True)
            storage_path = os.path.join(saleha_dir, "metrics.jsonl")
        self.storage_path = storage_path

    def record(self, event: str, **data: Any) -> None:
        """Append ek structured event. Failure kabhi caller ko nahi failta --
        observability pipeline production path tode nahi."""
        entry = {"ts": round(time.time(), 3), "event": event}
        entry.update(data)
        try:
            dirname = os.path.dirname(self.storage_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def tail(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Latest N events (chronological)."""
        if not os.path.isfile(self.storage_path):
            return []
        lines: List[str] = []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []
        out: List[Dict[str, Any]] = []
        for raw in reversed(lines[-limit:]):
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    def summary(self) -> Dict[str, Any]:
        """Poore JSONL ka aggregate -- runs/success-rate/attempts/models."""
        runs = [e for e in self.tail(limit=10_000) if e.get("event") == "run_completed"]
        total = len(runs)
        successes = sum(1 for r in runs if r.get("success"))
        attempts = [r.get("attempts", 0) or 0 for r in runs]
        durations = [r.get("duration_sec") for r in runs if isinstance(r.get("duration_sec"), (int, float))]

        by_model: Dict[str, Dict[str, int]] = {}
        for r in runs:
            model = str(r.get("model", "unknown"))
            slot = by_model.setdefault(model, {"runs": 0, "wins": 0})
            slot["runs"] += 1
            if r.get("success"):
                slot["wins"] += 1

        return {
            "total_runs": total,
            "successful_runs": successes,
            "failed_runs": total - successes,
            "success_rate": round(successes / total * 100, 1) if total else 0.0,
            "avg_attempts": round(sum(attempts) / total, 2) if total else 0.0,
            "avg_duration_sec": round(sum(durations) / len(durations), 2) if durations else 0.0,
            "by_model": by_model,
        }


# Global singleton (~/.saleha/metrics.jsonl)
metrics_tracker = MetricsTracker()
