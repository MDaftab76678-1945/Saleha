"""Unit and Integration Test Suite for Neuro-Symbolic Invariant Engine and SLM Distillation Suite."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from saleha.cli.chat_session import SwarmChatSession
from saleha.core.cognitive.neuro_symbolic_engine import (
    NeuroSymbolicEngine,
)
from saleha.core.training.dataset_synthesizer import (
    SalehaDatasetSynthesizer,
    dataset_synthesizer,
)
from saleha.core.training.model_distillation_pipeline import (
    ModelDistillationPipeline,
)


class TestNeuroSymbolicEngine:
    def test_score_valid_clean_code(self) -> None:
        engine = NeuroSymbolicEngine()
        code = """def add_numbers(a: int, b: int) -> int:
    \"\"\"Calculates sum of two integers.\"\"\"
    return a + b
"""
        score = engine.score_code(code)
        assert score.ast_valid is True
        assert score.type_safety_score == 1.0
        assert score.security_score == 1.0
        assert score.composite_score >= 0.9
        assert "AST: Clean Syntax" in score.feedback_notes[0]

    def test_score_syntax_error_code(self) -> None:
        engine = NeuroSymbolicEngine()
        code = "def broken(;"
        score = engine.score_code(code)
        assert score.ast_valid is False
        assert score.composite_score < 0.5
        assert "AST Syntax Error" in score.feedback_notes[0]

    def test_score_insecure_code(self) -> None:
        engine = NeuroSymbolicEngine()
        code = """import os
def dangerous_run(cmd: str):
    os.system(cmd)
"""
        score = engine.score_code(code)
        assert score.ast_valid is True
        assert score.security_score < 0.5

    def test_score_insecure_code_via_from_import_alias(self) -> None:
        # Regression guard: the security check used substring matching
        # ("os.system(" in code), which missed a realistic evasion --
        # importing the dangerous name under a local alias. Measured before
        # the fix: this scored "OWASP Top-10 SAST Clean" (1.0).
        engine = NeuroSymbolicEngine()
        code = """from os import system
def dangerous_run(cmd: str):
    system(cmd)
"""
        score = engine.score_code(code)
        assert score.ast_valid is True
        assert score.security_score < 0.5
        assert "High Risk" in " ".join(score.feedback_notes)

    def test_score_insecure_code_via_renamed_import(self) -> None:
        engine = NeuroSymbolicEngine()
        code = """from subprocess import call as run_shell
def dangerous_run(cmd):
    run_shell(cmd)
"""
        score = engine.score_code(code)
        assert score.security_score < 0.5

    def test_unrelated_os_import_is_not_flagged(self) -> None:
        # The fix must not turn every `from os import X` into a false
        # positive -- only the two specific dangerous names.
        engine = NeuroSymbolicEngine()
        code = """from os import path
def f():
    return path.exists(".")
"""
        score = engine.score_code(code)
        assert score.security_score == 1.0

    def test_rank_candidates(self) -> None:
        engine = NeuroSymbolicEngine()
        candidates = [
            "def broken(: pass",
            "def valid_typed(x: int) -> int:\n    return x * 2",
            "def dangerous():\n    eval('1+1')",
        ]
        ranked = engine.rank_candidates(candidates)
        assert len(ranked) == 3
        # Best candidate should be the valid_typed one
        assert "valid_typed" in ranked[0][0]
        assert ranked[0][1].composite_score > ranked[1][1].composite_score


class TestSalehaDatasetSynthesizer:
    def test_synthesize_dataset_chatml(self, tmp_path: Path) -> None:
        synthesizer = SalehaDatasetSynthesizer()
        out_file = str(tmp_path / "test_chatml.jsonl")
        count = synthesizer.synthesize_dataset(output_path=out_file, sample_count=10, format_type="chatml")
        seeds = synthesizer.get_dataset_summary()["total_seed_templates"]
        # Asking for 10 from 3 seeds writes 3, never repeats to reach 10.
        assert count == seeds
        assert os.path.exists(out_file)

        with open(out_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        assert len(lines) == seeds
        assert len({json.dumps(line, sort_keys=True) for line in lines}) == seeds
        assert "messages" in lines[0]
        assert lines[0]["messages"][0]["role"] == "system"

    def test_synthesize_dataset_alpaca(self, tmp_path: Path) -> None:
        synthesizer = SalehaDatasetSynthesizer()
        out_file = str(tmp_path / "test_alpaca.jsonl")
        count = synthesizer.synthesize_dataset(output_path=out_file, sample_count=2, format_type="alpaca")
        assert count == 2
        with open(out_file, "r", encoding="utf-8") as f:
            sample = json.loads(f.readline())
        assert "instruction" in sample
        assert "output" in sample

    def test_get_dataset_summary(self) -> None:
        summary = dataset_synthesizer.get_dataset_summary()
        assert summary["total_seed_templates"] >= 3
        assert "chatml" in summary["supported_formats"]
        assert "ast_validation" not in summary  # was a hardcoded "100%" claim
        assert summary["code_seeds_that_parse"] == summary["code_seeds"]

    def test_ring_buffer_seed_runs(self) -> None:
        seed = next(t for t in SalehaDatasetSynthesizer()._seed_templates if "ring buffer" in t["instruction"])
        ns: dict = {}
        exec(seed["output"], ns)  # saleha: allow-exec
        # Python 3.14 evaluates annotations lazily; resolving them here is what
        # a 3.12/3.13 interpreter does at def time (the seed used Any/Optional
        # without importing them).
        import typing
        typing.get_type_hints(ns["RingBuffer"].push)
        buf = ns["RingBuffer"](2)
        for item in (1, 2, 3):
            buf.push(item)
        assert [buf.pop(), buf.pop(), buf.pop()] == [2, 3, None]


class TestModelDistillationPipeline:
    def test_generate_lora_training_yaml(self, tmp_path: Path) -> None:
        pipeline = ModelDistillationPipeline()
        yaml_path = str(tmp_path / "lora_config.yaml")
        content = pipeline.generate_lora_training_yaml(yaml_path)
        assert "Qwen/Qwen2.5-Coder-1.5B-Instruct" in content
        assert "lora_r: 16" in content
        assert os.path.exists(yaml_path)

    def test_generate_training_script(self, tmp_path: Path) -> None:
        pipeline = ModelDistillationPipeline()
        script_path = str(tmp_path / "train.py")
        content = pipeline.generate_training_script(script_path)
        assert "Saleha-Coder SLM Distillation Pipeline" in content
        assert os.path.exists(script_path)
        # It used to print "Simulated Dry-Run Complete ... 100% Configured &
        # Validated" and return success when nothing could run.
        assert "100%" not in content and "Simulated" not in content
        assert "return 1" in content


class TestChatSessionNeuroSymbolicCommands:
    def test_chat_session_commands(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # /lora-config writes configs/ and scripts/ relative to the cwd; run it
        # in tmp_path so the suite stops overwriting the repo's own files.
        monkeypatch.chdir(tmp_path)
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)
        dataset_path = str(tmp_path / "chat_dataset.jsonl")

        assert session.process_command(f"/dataset {dataset_path}") is True
        assert session.process_command("/lora-config") is True
        assert session.process_command("/score-code def test_func(x: int) -> int: return x + 1") is True
