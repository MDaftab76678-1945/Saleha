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
            entry_id=f"tx_{len(self.entries) + 1}_{int(time.time() * 1000) % 10000}",
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

    def save(self):
        """Persists ledger to disk."""
        try:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self.entries], f, indent=2)
        except (OSError, IOError):
            pass  # noqa

    def _load(self):
        """Loads ledger from disk if available."""
        if not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [LedgerEntry(**d) for d in data]
        except (OSError, IOError, json.JSONDecodeError):
            pass  # noqa


token_ledger = TokenLedger()


if __name__ == "__main__":
    _ledger = TokenLedger()
    _ledger.record_transaction("task_1", "qwen2.5-coder:1.5b", 500, 300, saved_tokens=1200, duration_sec=1.5)
    _summary = _ledger.get_summary()
