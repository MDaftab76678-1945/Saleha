"""Unit and Integration Test Suite for Neuro-Symbolic Invariant Engine and SLM Distillation Suite."""

import os
import json
import pytest
from unittest.mock import MagicMock

from saleha.core.neuro_symbolic_engine import (
    NeuroSymbolicEngine,
    InvariantFitnessScore,
    neuro_symbolic_engine,
)
from saleha.core.dataset_synthesizer import (
    SalehaDatasetSynthesizer,
    dataset_synthesizer,
)
from saleha.core.model_distillation_pipeline import (
    ModelDistillationPipeline,
    model_distillation_pipeline,
)
from saleha.cli.chat_session import SwarmChatSession


class TestNeuroSymbolicEngine:
    def test_score_valid_clean_code(self):
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

    def test_score_syntax_error_code(self):
        engine = NeuroSymbolicEngine()
        code = "def broken(;"
        score = engine.score_code(code)
        assert score.ast_valid is False
        assert score.composite_score < 0.5
        assert "AST Syntax Error" in score.feedback_notes[0]

    def test_score_insecure_code(self):
        engine = NeuroSymbolicEngine()
        code = """import os
def dangerous_run(cmd: str):
    os.system(cmd)
"""
        score = engine.score_code(code)
        assert score.ast_valid is True
        assert score.security_score < 0.5

    def test_rank_candidates(self):
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
    def test_synthesize_dataset_chatml(self, tmp_path):
        synthesizer = SalehaDatasetSynthesizer()
        out_file = str(tmp_path / "test_chatml.jsonl")
        count = synthesizer.synthesize_dataset(output_path=out_file, sample_count=10, format_type="chatml")
        assert count == 10
        assert os.path.exists(out_file)

        with open(out_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        assert len(lines) == 10
        assert "messages" in lines[0]
        assert lines[0]["messages"][0]["role"] == "system"

    def test_synthesize_dataset_alpaca(self, tmp_path):
        synthesizer = SalehaDatasetSynthesizer()
        out_file = str(tmp_path / "test_alpaca.jsonl")
        count = synthesizer.synthesize_dataset(output_path=out_file, sample_count=5, format_type="alpaca")
        assert count == 5
        with open(out_file, "r", encoding="utf-8") as f:
            sample = json.loads(f.readline())
        assert "instruction" in sample
        assert "output" in sample

    def test_get_dataset_summary(self):
        summary = dataset_synthesizer.get_dataset_summary()
        assert summary["total_seed_templates"] >= 3
        assert "chatml" in summary["supported_formats"]


class TestModelDistillationPipeline:
    def test_generate_lora_training_yaml(self, tmp_path):
        pipeline = ModelDistillationPipeline()
        yaml_path = str(tmp_path / "lora_config.yaml")
        content = pipeline.generate_lora_training_yaml(yaml_path)
        assert "Qwen/Qwen2.5-Coder-1.5B-Instruct" in content
        assert "lora_r: 16" in content
        assert os.path.exists(yaml_path)

    def test_generate_training_script(self, tmp_path):
        pipeline = ModelDistillationPipeline()
        script_path = str(tmp_path / "train.py")
        content = pipeline.generate_training_script(script_path)
        assert "Saleha-Coder SLM Distillation Pipeline" in content
        assert os.path.exists(script_path)


class TestChatSessionNeuroSymbolicCommands:
    def test_chat_session_commands(self, tmp_path):
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)
        dataset_path = str(tmp_path / "chat_dataset.jsonl")

        assert session.process_command(f"/dataset {dataset_path}") is True
        assert session.process_command("/lora-config") is True
        assert session.process_command("/score-code def test_func(x: int) -> int: return x + 1") is True
