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

    @unittest.skipUnless(
        os.environ.get("SALEHA_RUN_GPU_TESTS") == "1",
        "real DPO training takes ~13 min of GPU time (1000 pairs) and hung the "
        "whole suite at 19%; set SALEHA_RUN_GPU_TESTS=1 to run it deliberately",
    )
    def test_lora_tuner_dpo(self):
        """Real DPO training attempt via trl.DPOTrainer against the real
        datasets/saleha_dpo_pairs.jsonl (1000 pairs). May succeed or fail
        depending on the local trl/torch install, but must never fabricate a
        result -- this replaces a prior version of this test that asserted
        a guaranteed 76.5->92.4 hardcoded-score improvement.

        Opt-in: this is a genuine end-to-end training run, not a unit test.
        Skipping it by default is what makes the suite finishable at all;
        the test itself is unchanged and still real when enabled."""
        tuner = LoRATuner()
        res = tuner.tune_dpo()
        self.assertEqual(res.output_model, "saleha-dpo-slm")
        self.assertGreater(res.samples_used, 0)
        if res.success:
            self.assertIsInstance(res.after_score, float)
            self.assertIsInstance(res.before_score, float)
        else:
            self.assertTrue(res.error, "a failed real DPO run must report a real error, not a silent/fake success")
