"""
Saleha Core: Stats Tracker (New file -- fixes the persistence gap)

Problem this solves:
The CLI showed things like "qwen3.5:0.8b -- 16 uses, 100% success" but this
lived only in memory. Restart Saleha and it's gone -- the router can never
actually learn across sessions.

This module stores per-model stats in a JSON file (~/.saleha/stats.json by
default), similar in spirit to Intent Kernel's ~/.intent-kernel/memory.json.

Usage:
    tracker = StatsTracker()
    tracker.record(model="qwen3.5:0.8b", task_type="coding", success=True, attempts=1)
    stats = tracker.get_model_stats("qwen3.5:0.8b")
    best = tracker.best_model_for(task_type="coding")
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


DEFAULT_STATS_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "stats.json")


@dataclass
class ModelStats:
    uses: int = 0
    successes: int = 0
    total_attempts: int = 0
    last_used: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.uses == 0:
            return 0.0
        return round(100 * self.successes / self.uses, 1)

    @property
    def avg_attempts(self) -> float:
        if self.uses == 0:
            return 0.0
        return round(self.total_attempts / self.uses, 2)


class StatsTracker:
    def __init__(self, path: str = DEFAULT_STATS_PATH):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Corrupt file shouldn't crash Saleha -- back it up and start fresh.
            backup_path = self.path + ".corrupt"
            try:
                os.replace(self.path, backup_path)
                print(f"[StatsTracker] warning: {self.path} was corrupt ({e}); "
                      f"backed up to {backup_path} and starting fresh.")
            except OSError:
                pass
            return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # Write to temp file then replace -- avoids a half-written file if
        # the process dies mid-write.
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self.path)

    def record(
        self,
        model: str,
        success: bool,
        attempts: int = 1,
        task_type: str = "general",
    ):
        """Ek task ka result record karo. task_type se alag category track hoti hai
        (e.g. 'coding' vs 'chat') taaki router har category ke liye alag best-model
        nikal sake."""
        bucket = self._data.setdefault(task_type, {})
        entry = bucket.setdefault(model, {
            "uses": 0, "successes": 0, "total_attempts": 0, "last_used": None,
        })
        entry["uses"] += 1
        entry["successes"] += 1 if success else 0
        entry["total_attempts"] += attempts
        entry["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def get_model_stats(self, model: str, task_type: str = "general") -> ModelStats:
        entry = self._data.get(task_type, {}).get(model)
        if not entry:
            return ModelStats()
        return ModelStats(
            uses=entry["uses"],
            successes=entry["successes"],
            total_attempts=entry["total_attempts"],
            last_used=entry.get("last_used"),
        )

    def best_model_for(self, task_type: str = "general", min_uses: int = 2) -> Optional[str]:
        """Sabse zyada success-rate wala model return karta hai (jinke paas kam-se-kam
        min_uses data points hain, taaki 1-use-100%-success flukes na jeetein)."""
        bucket = self._data.get(task_type, {})
        candidates = []
        for model, entry in bucket.items():
            if entry["uses"] >= min_uses:
                rate = entry["successes"] / entry["uses"]
                candidates.append((rate, model))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    def summary(self, task_type: str = "general") -> str:
        bucket = self._data.get(task_type, {})
        if not bucket:
            return f"No stats yet for task_type='{task_type}'."
        lines = [f"Stats for task_type='{task_type}':"]
        for model, entry in sorted(bucket.items(), key=lambda kv: -kv[1]["uses"]):
            stats = self.get_model_stats(model, task_type)
            lines.append(
                f"  {model}: {stats.uses} uses, {stats.success_rate}% success, "
                f"avg {stats.avg_attempts} attempts, last used {stats.last_used}"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile

    # Use a throwaway path for the demo so it doesn't touch a real ~/.saleha
    with tempfile.TemporaryDirectory() as tmp:
        demo_path = os.path.join(tmp, "stats.json")
        tracker = StatsTracker(path=demo_path)

        tracker.record(model="qwen3.5:0.8b", success=True, attempts=1, task_type="coding")
        tracker.record(model="qwen3.5:0.8b", success=True, attempts=1, task_type="coding")
        tracker.record(model="qwen3.5:0.8b", success=False, attempts=3, task_type="coding")
        tracker.record(model="deepseek-coder:6.7b", success=True, attempts=1, task_type="coding")

        print(tracker.summary(task_type="coding"))
        print("\nBest model for coding:", tracker.best_model_for(task_type="coding"))

        # Prove persistence: reload from the same file
        tracker2 = StatsTracker(path=demo_path)
        print("\nReloaded from disk:")
        print(tracker2.summary(task_type="coding"))