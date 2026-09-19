"""
Saleha Core: Double-Entry Token Economics & ROI Ledger (TokenLedger)

Maintains double-entry accounting for agent token usage and compute economics:
1. Debits: Prompt tokens, completion tokens, execution seconds consumed.
2. Credits: Memory recall token savings, self-healing fast-path credits.
3. Computes exact financial ROI and compute efficiency metrics.
4. Persistent storage in ~/.saleha/token_ledger.json.
"""

import os
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass
class LedgerEntry:
    """Represents a single double-entry token transaction."""
    entry_id: str
    task_id: str
    model: str
    prompt_tokens_debit: int
    completion_tokens_debit: int
    saved_tokens_credit: int
    compute_duration_sec: float
    timestamp: float = field(default_factory=time.time)
    note: str = ""


class TokenLedger:
    """Double-entry token and compute ROI ledger."""

    DEFAULT_STORE = os.path.expanduser("~/.saleha/token_ledger.json")
    ESTIMATED_COST_PER_1K_TOKENS = 0.002  # $0.002 / 1K tokens standard reference

    def __init__(self, store_path: Optional[str] = None):
        """Initializes the token economics ledger."""
        self.store_path = store_path or self.DEFAULT_STORE
        self.entries: List[LedgerEntry] = []
        self._load()

    def record_transaction(
        self,
        task_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        saved_tokens: int = 0,
        duration_sec: float = 0.0,
        note: str = "",
    ) -> LedgerEntry:
        """Records a new double-entry token and compute transaction."""
        entry = LedgerEntry(
            entry_id=f"tx_{len(self.entries) + 1}_{uuid.uuid4().hex[:6]}",
            task_id=task_id,
            model=model,
            prompt_tokens_debit=prompt_tokens,
            completion_tokens_debit=completion_tokens,
            saved_tokens_credit=saved_tokens,
            compute_duration_sec=duration_sec,
            note=note,
        )
        self.entries.append(entry)
        self.save()
        return entry

    def get_summary(self) -> Dict[str, Any]:
        """Calculates total debits, credits, cost savings, and compute ROI."""
        total_prompt = sum(e.prompt_tokens_debit for e in self.entries)
        total_completion = sum(e.completion_tokens_debit for e in self.entries)
        total_consumed = total_prompt + total_completion
        total_saved = sum(e.saved_tokens_credit for e in self.entries)
        total_sec = sum(e.compute_duration_sec for e in self.entries)

        est_spent_usd = round((total_consumed / 1000.0) * self.ESTIMATED_COST_PER_1K_TOKENS, 4)
        est_saved_usd = round((total_saved / 1000.0) * self.ESTIMATED_COST_PER_1K_TOKENS, 4)
        roi_pct = round((total_saved / total_consumed * 100), 1) if total_consumed > 0 else 0.0

        return {
            "total_transactions": len(self.entries),
            "total_tokens_consumed": total_consumed,
            "total_tokens_saved": total_saved,
            "estimated_spend_usd": est_spent_usd,
            "estimated_savings_usd": est_saved_usd,
            "compute_time_sec": round(total_sec, 2),
            "token_roi_percent": roi_pct,
        }

    def filter_by_model(self, model: str) -> List[LedgerEntry]:
        """Filters ledger entries produced by a specific model."""
        target = model.strip().lower()
        return [e for e in self.entries if e.model.strip().lower() == target]

    def filter_by_task(self, task_id: str) -> List[LedgerEntry]:
        """Filters ledger entries matching a given task ID."""
        return [e for e in self.entries if e.task_id == task_id]

    def clear(self) -> None:
        """Clears all transactions in memory and on disk."""
        self.entries = []
        self.save()

    def export_json(self, target_path: str) -> bool:
        """Exports ledger entries to an external JSON file."""
        try:
            target_dir = os.path.dirname(os.path.abspath(target_path))
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self.entries], f, indent=2)
            return True
        except (OSError, IOError):
            return False

    def import_json(self, source_path: str, overwrite: bool = False) -> int:
        """Imports ledger transactions from an external JSON file."""
        if not os.path.isfile(source_path):
            return 0
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return 0
            if overwrite:
                self.entries = []
            count = 0
            existing_ids = {e.entry_id for e in self.entries}
            for d in data:
                entry = LedgerEntry(**d)
                if entry.entry_id not in existing_ids:
                    self.entries.append(entry)
                    existing_ids.add(entry.entry_id)
                    count += 1
            if count > 0 or overwrite:
                self.save()
            return count
        except Exception:
            return 0

    def save(self) -> bool:
        """Persists ledger to disk atomically."""
        tmp_path = None
        try:
            store_dir = os.path.dirname(os.path.abspath(self.store_path))
            if store_dir:
                os.makedirs(store_dir, exist_ok=True)
            tmp_path = f"{self.store_path}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self.entries], f, indent=2)
            os.replace(tmp_path, self.store_path)
            return True
        except (OSError, IOError):
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False

    def _load(self) -> None:
        """Loads ledger from disk if available."""
        if not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [LedgerEntry(**d) for d in data]
        except (OSError, IOError, json.JSONDecodeError):
            pass


token_ledger = TokenLedger()


if __name__ == "__main__":
    _ledger = TokenLedger()
    _ledger.record_transaction("task_1", "qwen2.5-coder:3b", 500, 300, saved_tokens=1200, duration_sec=1.5)
    _summary = _ledger.get_summary()
