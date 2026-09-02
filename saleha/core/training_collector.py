"""
Saleha Core: Automatic Training Dataset Collector

Automatically harvests high-quality (task, solution) pairs from past
Saleha sessions to build fine-tuning datasets for local Ollama models.
Kills OpenAI fine-tuning API ($8/MTok) — does it locally for $0.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


DEFAULT_DATASET_DIR = os.path.join(os.path.expanduser("~"), ".saleha", "training_data")


@dataclass
class TrainingSample:
    sample_id: str
    prompt: str
    completion: str
    quality_score: float    # 0.0 to 1.0 (based on test pass rate)
    source: str             # "session" | "manual" | "swe_bench"
    tags: List[str] = field(default_factory=list)
    timestamp: str = ""

    def to_alpaca(self) -> Dict[str, str]:
        """Alpaca-format dict (compatible with most fine-tuning frameworks)."""
        return {
            "instruction": self.prompt,
            "input": "",
            "output": self.completion,
        }

    def to_sharegpt(self) -> Dict[str, Any]:
        """ShareGPT format (compatible with Unsloth, axolotl)."""
        return {
            "conversations": [
                {"from": "human", "value": self.prompt},
                {"from": "gpt", "value": self.completion},
            ]
        }


class TrainingCollector:
    """
    Harvests fine-tuning data from Saleha sessions and manages
    the training dataset lifecycle.
    """

    def __init__(self, dataset_dir: str = DEFAULT_DATASET_DIR):
        self.dataset_dir = dataset_dir
        os.makedirs(dataset_dir, exist_ok=True)
        self._path = os.path.join(dataset_dir, "saleha_training.jsonl")

    def add_sample(self, prompt: str, completion: str,
                   quality_score: float = 1.0, source: str = "manual",
                   tags: Optional[List[str]] = None) -> TrainingSample:
        """Add a new training sample to the dataset."""
        import hashlib
        sample_id = hashlib.sha256(f"{prompt}{completion}{time.time()}".encode()).hexdigest()[:16]
        sample = TrainingSample(
            sample_id=sample_id,
            prompt=prompt[:2000],
            completion=completion[:4000],
            quality_score=max(0.0, min(1.0, quality_score)),
            source=source,
            tags=tags or [],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample.__dict__, ensure_ascii=False) + "\n")
        return sample

    def load_samples(self, min_quality: float = 0.7,
                     source_filter: Optional[str] = None) -> List[TrainingSample]:
        """Load training samples filtered by quality and source."""
        samples = []
        if not os.path.exists(self._path):
            return samples
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("quality_score", 0) < min_quality:
                        continue
                    if source_filter and data.get("source") != source_filter:
                        continue
                    tags = data.pop("tags", [])
                    sample = TrainingSample(**data, tags=tags)
                    samples.append(sample)
                except Exception:
                    continue
        return samples

    def export_alpaca(self, output_path: str, min_quality: float = 0.7) -> int:
        """Export dataset in Alpaca JSON format for fine-tuning."""
        parent_dir = os.path.dirname(os.path.abspath(output_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        samples = self.load_samples(min_quality=min_quality)
        data = [s.to_alpaca() for s in samples]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return len(data)

    def export_sharegpt(self, output_path: str, min_quality: float = 0.7) -> int:
        """Export dataset in ShareGPT JSONL format for Unsloth/axolotl."""
        parent_dir = os.path.dirname(os.path.abspath(output_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        samples = self.load_samples(min_quality=min_quality)
        with open(output_path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s.to_sharegpt(), ensure_ascii=False) + "\n")
        return len(samples)

    def stats(self) -> Dict[str, Any]:
        """Return dataset statistics."""
        all_samples = self.load_samples(min_quality=0.0)
        if not all_samples:
            return {"total": 0, "avg_quality": 0.0, "sources": {}}
        sources: Dict[str, int] = {}
        for s in all_samples:
            sources[s.source] = sources.get(s.source, 0) + 1
        avg_q = sum(s.quality_score for s in all_samples) / len(all_samples)
        return {
            "total": len(all_samples),
            "high_quality": sum(1 for s in all_samples if s.quality_score >= 0.8),
            "avg_quality": round(avg_q, 3),
            "sources": sources,
            "dataset_path": self._path,
        }


# Global instance
training_collector = TrainingCollector()

