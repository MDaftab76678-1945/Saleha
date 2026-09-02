"""Unit & Integration Test Suite for Polyglot DPO Dataset Engine and DPO LoRA Fine-Tuner."""

import os
import json
import pytest
import unittest

from saleha.core.dpo_dataset_engine import (
    SalehaDPODatasetEngine,
    DPOPreferencePair,
    SFTInstructionSample,
    dpo_dataset_engine,
)
from saleha.core.lora_tuner import LoRATuner, TuningConfig


class TestDPODatasetEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join("scratch", "test_dpo_out")
        self.engine = SalehaDPODatasetEngine(output_dir=self.temp_dir)

    def test_build_dataset_counts(self):
        dpo_count, sft_count = self.engine.build_dataset(target_count=50)
        self.assertGreaterEqual(dpo_count, 50)
        self.assertEqual(dpo_count, sft_count)

    def test_dpo_pair_schema(self):
        self.engine.build_dataset(target_count=10)
        pair = self.engine.dpo_pairs[0]
        self.assertTrue(pair.prompt)
        self.assertTrue(pair.chosen)
        self.assertTrue(pair.rejected)
        self.assertIn(pair.language, ["python", "typescript", "go", "rust", "sql", "Python", "TypeScript", "Go", "Rust", "SQL"])
        
        d = pair.to_dict()
        self.assertIn("chosen", d)
        self.assertIn("rejected", d)
        self.assertEqual(d["margin_score"], 1.0)

    def test_export_files(self):
        self.engine.build_dataset(target_count=20)
        dpo_file = self.engine.export_dpo_jsonl()
        sft_file = self.engine.export_sft_jsonl()
        alpaca_file = self.engine.export_alpaca_json()

        self.assertTrue(os.path.exists(dpo_file))
        self.assertTrue(os.path.exists(sft_file))
        self.assertTrue(os.path.exists(alpaca_file))

        # Check line count
        with open(dpo_file, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        self.assertGreaterEqual(len(lines), 20)

    def test_lora_tuner_dpo(self):
        tuner = LoRATuner()
        res = tuner.tune_dpo()
        self.assertTrue(res.success)
        self.assertEqual(res.output_model, "saleha-dpo-slm")
        self.assertGreater(res.after_score, res.before_score)
        self.assertGreater(res.improvement_pct, 0.0)
