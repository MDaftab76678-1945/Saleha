"""Integrity checks on the training data shipped in datasets/.

On 2026-09-23 three of these files held 1000 rows each with only 22 distinct
answers: 994 rows were one stub per language with a topic name pasted in,
returning {"status": "SUCCESS"}. Another file repeated 3 examples to 50 rows.
These tests fail if padded or duplicated data is written back.
"""

from __future__ import annotations

import ast
import glob
import json
import os
import re
from typing import Any, Dict, List

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_FILES = sorted(glob.glob(os.path.join(REPO_ROOT, "datasets", "*.json*")))
TRAINING_SCRIPTS = sorted(set(
    glob.glob(os.path.join(REPO_ROOT, "scripts", "train_*gpu*.py"))
    + [os.path.join(REPO_ROOT, "scripts", "train_real_qwen_lora.py")]
))


def _load(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            return [json.loads(line) for line in f if line.strip()]
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def _answer(row: Dict[str, Any]) -> str:
    for key in ("conversations", "messages"):
        if key in row:
            return " ".join(m.get("value") or m.get("content", "") for m in row[key]
                            if m.get("from", m.get("role")) in ("gpt", "assistant"))
    return row.get("chosen") or row.get("output") or row.get("response") or ""


def _names(paths: List[str]) -> List[str]:
    return [os.path.basename(p) for p in paths]


@pytest.mark.parametrize("path", DATA_FILES, ids=_names(DATA_FILES))
def test_no_duplicate_rows(path: str) -> None:
    rows = _load(path)
    keys = [json.dumps(r, sort_keys=True) for r in rows]
    assert len(set(keys)) == len(keys), f"{len(keys) - len(set(keys))} duplicate rows"


@pytest.mark.parametrize("path", DATA_FILES, ids=_names(DATA_FILES))
def test_answers_are_not_one_template_repeated(path: str) -> None:
    answers = [_answer(r) for r in _load(path)]
    if not answers:
        return
    assert len(set(answers)) == len(answers), "several prompts share one answer"
    stripped = {re.sub(r"\d+", "#", a) for a in answers}
    assert len(stripped) == len(answers), "answers differ only by numbers"


def test_no_stub_topic_rows_anywhere() -> None:
    for path in DATA_FILES:
        for row in _load(path):
            text = json.dumps(row)
            assert "(Task #" not in text, os.path.basename(path)
            assert '\\"status\\": \\"SUCCESS\\", \\"topic\\"' not in text, os.path.basename(path)


def test_dpo_pairs_are_real_preferences() -> None:
    path = os.path.join(REPO_ROOT, "datasets", "saleha_dpo_pairs.jsonl")
    if not os.path.exists(path):
        pytest.skip("no DPO pairs file (the padded datasets were removed on 2026-09-24)")
    rows = _load(path)
    assert rows
    for r in rows:
        assert r["chosen"] != r["rejected"]
        if r["language"] == "python":
            ast.parse(r["chosen"])


@pytest.mark.parametrize("path", TRAINING_SCRIPTS, ids=_names(TRAINING_SCRIPTS))
def test_training_script_refuses_tiny_datasets(path: str) -> None:
    """Every Dataset.from_list / from_dict call is preceded by the minimum-size guard, so
    an empty or near-empty file cannot silently produce an adapter."""
    src = open(path, "r", encoding="utf-8").read()
    ast.parse(src)
    assert re.search(r"^MIN_TRAINING_SAMPLES = \d+", src, re.M)
    guard = src.find("< MIN_TRAINING_SAMPLES:")
    uses = [i for i in (src.find("Dataset.from_list("), src.find("Dataset.from_dict(")) if i >= 0]
    assert uses and 0 <= guard < min(uses)
