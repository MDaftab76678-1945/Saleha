"""Saleha Alignment: Human Feedback (RLHF) & Direct Preference Optimization (DPO) Store.

Maintains persistent developer preferences and compiles unified DPO datasets:
1. SQLite persistence for developer approval/rejection signals and code diffs.
2. Contrastive pair curation merging RLHVR, RLAIF, RLCD, and RLHF.
3. Exporters for HuggingFace TRL (DPOTrainer) and Unsloth.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from saleha.core.dpo_dataset_engine import DPOPreferencePair


@dataclass
class HumanFeedback:
    """Developer evaluation for a generated solution."""
    feedback_id: str
    task_id: str
    prompt: str
    candidate_code: str
    rating: float  # +1.0 (approved), -1.0 (rejected), 0.0 (neutral)
    feedback_text: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "task_id": self.task_id,
            "prompt": self.prompt,
            "candidate_code": self.candidate_code,
            "rating": self.rating,
            "feedback_text": self.feedback_text,
            "timestamp": self.timestamp,
        }


class RLHFStore:
    """Persistent database for human feedback and contrastive alignment pairs."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            base_dir = Path.home() / ".saleha" / "alignment"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "preferences.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self) -> None:
        """Initializes SQLite schema for developer feedback and curated pairs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    candidate_code TEXT NOT NULL,
                    rating REAL NOT NULL,
                    feedback_text TEXT,
                    timestamp REAL NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contrastive_pairs (
                    pair_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    chosen TEXT NOT NULL,
                    rejected TEXT NOT NULL,
                    margin_score REAL NOT NULL,
                    source TEXT NOT NULL,
                    language TEXT DEFAULT 'python',
                    category TEXT DEFAULT 'alignment',
                    timestamp REAL NOT NULL
                );
            """)
            conn.commit()

    def record_feedback(
        self,
        task_id: str,
        prompt: str,
        candidate_code: str,
        rating: float,
        feedback_text: str = "",
    ) -> HumanFeedback:
        """Stores developer thumbs-up (+1.0) or thumbs-down (-1.0)."""
        feedback_id = f"fb_{uuid.uuid4().hex[:8]}"
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO human_feedback (feedback_id, task_id, prompt, candidate_code, rating, feedback_text, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (feedback_id, task_id, prompt, candidate_code, rating, feedback_text, now),
            )
            conn.commit()

        return HumanFeedback(
            feedback_id=feedback_id,
            task_id=task_id,
            prompt=prompt,
            candidate_code=candidate_code,
            rating=rating,
            feedback_text=feedback_text,
            timestamp=now,
        )

    def record_pair(
        self,
        prompt: str,
        chosen: str,
        rejected: str,
        margin_score: float = 1.0,
        source: str = "rlhf",
        language: str = "python",
        category: str = "alignment",
    ) -> DPOPreferencePair:
        """Persists a verified (chosen, rejected) contrastive pair."""
        pair_id = f"pair_{uuid.uuid4().hex[:8]}"
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO contrastive_pairs (pair_id, prompt, chosen, rejected, margin_score, source, language, category, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (pair_id, prompt, chosen, rejected, margin_score, source, language, category, now),
            )
            conn.commit()

        return DPOPreferencePair(
            pair_id=pair_id,
            prompt=prompt,
            chosen=chosen,
            rejected=rejected,
            language=language,
            category=category,
            margin_score=margin_score,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Returns physical stats on developer feedback and stored pairs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), AVG(rating) FROM human_feedback;")
            fb_row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM contrastive_pairs;")
            pair_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM human_feedback WHERE rating > 0;")
            positive_fb = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM human_feedback WHERE rating < 0;")
            negative_fb = cursor.fetchone()[0]

        return {
            "total_feedback_entries": fb_row[0] if fb_row else 0,
            "average_human_rating": round(fb_row[1], 3) if fb_row and fb_row[1] is not None else 0.0,
            "positive_feedback_count": positive_fb,
            "negative_feedback_count": negative_fb,
            "total_contrastive_pairs": pair_count,
            "db_path": str(self.db_path),
        }

    def list_pairs(self, min_margin: float = 0.0, limit: int = 100) -> List[DPOPreferencePair]:
        """Retrieves stored preference pairs filtered by minimum margin."""
        pairs: List[DPOPreferencePair] = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT pair_id, prompt, chosen, rejected, language, category, margin_score
                FROM contrastive_pairs
                WHERE margin_score >= ?
                ORDER BY margin_score DESC, timestamp DESC
                LIMIT ?;
                """,
                (min_margin, limit),
            )
            for row in cursor.fetchall():
                pairs.append(
                    DPOPreferencePair(
                        pair_id=row[0],
                        prompt=row[1],
                        chosen=row[2],
                        rejected=row[3],
                        language=row[4],
                        category=row[5],
                        margin_score=row[6],
                    )
                )
        return pairs


class DPOBatchExporter:
    """Compiles unified DPO datasets for local SLM post-training."""

    def __init__(self, store: Optional[RLHFStore] = None) -> None:
        self.store = store or RLHFStore()

    def export_to_jsonl(
        self,
        output_path: str | Path,
        min_margin: float = 0.15,
        limit: int = 1000,
    ) -> int:
        """Exports pairs in HuggingFace TRL DPOTrainer format."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        pairs = self.store.list_pairs(min_margin=min_margin, limit=limit)
        with open(out_file, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair.to_dict()) + "\n")

        return len(pairs)
