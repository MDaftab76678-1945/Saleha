"""SalehaDatasetSynthesizer: writes the hand-written seed samples as a fine-tuning file.

It writes each seed once. An earlier version cycled the three seeds to fill
`sample_count` rows and reported that padded count as synthesized samples.
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DatasetSample:
    """Represents a fine-tuning dataset instruction sample."""
    instruction: str
    input_context: str
    output_response: str
    category: str  # coding, architecture, security, qa, refactor
    format_type: str = "chatml"


class SalehaDatasetSynthesizer:
    """Exports curated seed samples in ChatML, Alpaca or ShareGPT format."""

    def __init__(self):
        self._seed_templates = [
            {
                "instruction": "Synthesize a high-throughput ring buffer in Python with ASan-compatible boundary checks.",
                "input": "",
                "output": """from typing import Any, Optional


class RingBuffer:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.head = 0
        self.tail = 0
        self.size = 0

    def push(self, item: Any) -> None:
        self.buffer[self.tail] = item
        self.tail = (self.tail + 1) % self.capacity
        if self.size < self.capacity:
            self.size += 1
        else:
            self.head = (self.head + 1) % self.capacity

    def pop(self) -> Optional[Any]:
        if self.size == 0:
            return None
        item = self.buffer[self.head]
        self.buffer[self.head] = None
        self.head = (self.head + 1) % self.capacity
        self.size -= 1
        return item""",
                "category": "coding",
            },
            {
                "instruction": "Audit Python code for OWASP Top-10 security vulnerabilities and propose remediation.",
                "input": "eval(user_input)",
                "output": "Vulnerability Identified: CWE-95 (Improper Neutralization of Directives in Dynamically Evaluated Code).\nRemediation: Replace `eval()` with `ast.literal_eval()` or a strictly validated schema parser.",
                "category": "security",
            },
            {
                "instruction": "Generate an automated Pytest test suite for a distributed cache with TTL eviction.",
                "input": "",
                "output": """import pytest
import time

def test_cache_set_and_get():
    cache = TTLCache(ttl_seconds=1)
    cache.set("key", "value")
    assert cache.get("key") == "value"

def test_cache_ttl_expiration():
    cache = TTLCache(ttl_seconds=0.1)
    cache.set("key", "value")
    time.sleep(0.15)
    assert cache.get("key") is None""",
                "category": "qa",
            },
        ]

    def synthesize_dataset(
        self,
        output_path: str = "datasets/saleha_train_dataset.jsonl",
        sample_count: Optional[int] = None,
        format_type: str = "chatml",
    ) -> int:
        """Writes each seed sample once and returns how many were written.

        `sample_count` caps the output; it never repeats seeds to reach it.
        """
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        samples_written = 0
        seeds = self._seed_templates
        if sample_count is not None:
            seeds = seeds[:max(0, sample_count)]

        with open(output_path, "w", encoding="utf-8") as f:
            for template in seeds:
                
                if format_type == "chatml":
                    record = {
                        "messages": [
                            {"role": "system", "content": "You are Saleha-Coder, a careful software engineer."},
                            {"role": "user", "content": template["instruction"] + (f"\nInput:\n{template['input']}" if template['input'] else "")},
                            {"role": "assistant", "content": template["output"]},
                        ]
                    }
                elif format_type == "alpaca":
                    record = {
                        "instruction": template["instruction"],
                        "input": template["input"],
                        "output": template["output"],
                    }
                else:  # sharegpt
                    record = {
                        "conversations": [
                            {"from": "human", "value": template["instruction"]},
                            {"from": "gpt", "value": template["output"]},
                        ]
                    }

                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                samples_written += 1

        return samples_written

    def get_dataset_summary(self) -> Dict[str, Any]:
        """Returns statistics on the seed samples, measured rather than asserted."""
        code_seeds = [t for t in self._seed_templates if t["category"] in ("coding", "qa")]
        parsing = 0
        for t in code_seeds:
            try:
                ast.parse(t["output"])
                parsing += 1
            except SyntaxError:
                pass
        return {
            "total_seed_templates": len(self._seed_templates),
            "supported_formats": ["chatml", "alpaca", "sharegpt"],
            "categories": sorted({t["category"] for t in self._seed_templates}),
            "code_seeds": len(code_seeds),
            "code_seeds_that_parse": parsing,
        }


dataset_synthesizer = SalehaDatasetSynthesizer()
