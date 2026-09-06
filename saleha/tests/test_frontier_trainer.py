"""Test suite for the Frontier Trainer & Benchmark Alignment Engine.

Rewritten against the real (non-fabricated) implementation: every phase
either does real work or is honestly reported as skipped/unimplemented.
"""

import os
import shutil
import tempfile
import unittest

from saleha.core.frontier_trainer import FrontierTrainer, frontier_trainer, TrainingRunReport
from saleha.core.training_collector import TrainingCollector


class TestFrontierTrainer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.trainer = FrontierTrainer(work_dir=self.tmp)
        # Isolate training data so this test doesn't depend on (or pollute) real session data.
        self.trainer.tuner.collector = TrainingCollector(dataset_dir=self.tmp)
        for i in range(6):
            self.trainer.tuner.collector.add_sample(
                f"Write a Python function that returns {i}.",
                f"def func_{i}():\n    return {i}",
                quality_score=0.9,
            )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_training_real_sft_and_honest_skips(self):
        report: TrainingRunReport = self.trainer.run_training(
            base_model="qwen2.5-coder:0.5b",
            output_model="saleha-test-model",
            epochs=1,
            enable_dpo=True,
            deploy_to_ollama=False,
            run_benchmark=False,
        )
        self.assertTrue(report.run_id)
        self.assertEqual(report.target_model_name, "saleha-test-model")

        # Phase 1 (SFT) is real and must have produced an actual adapter.
        self.assertTrue(any("Phase 1" in p for p in report.phases_completed), report.phases_skipped)
        self.assertIsNotNone(report.sft_result)
        self.assertTrue(report.sft_result.success, report.sft_result.error)
        self.assertTrue(os.path.exists(os.path.join(report.adapter_artifact_path, "adapter_model.safetensors")))

        # Phase 2 (DPO) has no real preference dataset in this environment,
        # so it must be honestly skipped -- never fabricated.
        self.assertEqual(report.total_dpo_pairs, 0)
        self.assertTrue(any("Phase 2" in p and "SKIPPED" in p for p in report.phases_skipped))

        # Phase 3 (RLIF) must always self-report as not implemented -- no fake benchmark table.
        self.assertTrue(any("Phase 3" in p and "NOT IMPLEMENTED" in p for p in report.phases_skipped))

        # No fabricated GGUF/benchmark fields exist on the report anymore.
        self.assertFalse(hasattr(report, "gguf_path"))
        self.assertFalse(hasattr(report, "benchmarks"))

    def test_dpo_skipped_reason_names_missing_dataset(self):
        report = self.trainer.run_training(
            base_model="qwen2.5-coder:0.5b", output_model="saleha-test-model-2",
            epochs=1, enable_dpo=True, deploy_to_ollama=False, run_benchmark=False,
        )
        skip_msgs = [p for p in report.phases_skipped if p.startswith("Phase 2")]
        self.assertEqual(len(skip_msgs), 1)
        self.assertIn("saleha_dpo_pairs.jsonl", skip_msgs[0])


if __name__ == "__main__":
    unittest.main()
