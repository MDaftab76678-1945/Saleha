"""
Saleha Core: Task History (New file)

Har task run ka poora record save karta hai -- kya goal tha, kaunsa model use
hua, success mila ya nahi, kitne attempts lage, aur final code kya bana.

File format: JSONL (ek line = ek task), taaki file corrupt hone ka risk kam
ho -- agar ek line kharab bhi ho jaaye, baaki history padhi ja sakti hai.

Default location: ~/.saleha/history.jsonl

Usage:
    history = TaskHistory()
    history.log(goal="...", model="qwen2.5-coder:1.5b", success=True,
                attempts=1, code="...")
    recent = history.recent(5)          # last 5 tasks
    failed = history.failed_tasks()     # sirf jo fail hue
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import List, Optional


DEFAULT_HISTORY_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "history.jsonl")


@dataclass
class TaskRecord:
    timestamp: str
    goal: str
    model: str
    success: bool
    attempts: int
    code: str
    error: Optional[str] = None


class TaskHistory:
    def __init__(self, path: str = DEFAULT_HISTORY_PATH):
        self.path = path

    def log(
        self,
        goal: str,
        model: str,
        success: bool,
        attempts: int,
        code: str = "",
        error: Optional[str] = None,
    ):
        record = TaskRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            goal=goal,
            model=model,
            success=success,
            attempts=attempts,
            code=code,
            error=error,
        )
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # Append-only -- ek task ek line, koi read-modify-write race nahi
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _read_all(self) -> List[TaskRecord]:
        if not os.path.exists(self.path):
            return []
        records = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(TaskRecord(**data))
                except (json.JSONDecodeError, TypeError) as e:
                    # Ek kharab line pura history nahi todegi -- skip karo, warn karo
                    print(f"[TaskHistory] warning: skipping corrupt line {line_num}: {e}")
        return records

    def recent(self, n: int = 10) -> List[TaskRecord]:
        if n <= 0:
            return []
        return self._read_all()[-n:]

    def failed_tasks(self) -> List[TaskRecord]:
        return [r for r in self._read_all() if not r.success]

    def all(self) -> List[TaskRecord]:
        return self._read_all()

    def summary(self, n: int = 10) -> str:
        records = self.recent(n)
        if not records:
            return "No task history yet."
        lines = [f"Last {len(records)} tasks:"]
        for r in records:
            status = "✅" if r.success else "❌"
            lines.append(
                f"  {status} [{r.timestamp}] ({r.model}, {r.attempts} attempt(s)): {r.goal[:60]}"
            )
        return "\n".join(lines)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        demo_path = os.path.join(tmp, "history.jsonl")
        history = TaskHistory(path=demo_path)

        history.log(
            goal="Create a function to add two numbers",
            model="qwen2.5-coder:1.5b",
            success=True,
            attempts=1,
            code="def add(a, b): return a + b",
        )
        history.log(
            goal="Create a broken REST API",
            model="qwen3.5:0.8b",
            success=False,
            attempts=3,
            code="",
            error="SyntaxError on line 4",
        )

        print(history.summary())
        print(f"\nFailed tasks: {len(history.failed_tasks())}")

        # Prove persistence across a fresh instance
        history2 = TaskHistory(path=demo_path)
        print("\nReloaded from disk:")
        print(history2.summary())