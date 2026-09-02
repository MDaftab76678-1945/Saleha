"""Unit & Integration Test Suite for Frontier Trainer & Benchmark Alignment Engine."""

import os
import unittest

from saleha.core.frontier_trainer import FrontierTrainer, frontier_trainer, TrainingRunReport, BenchmarkTarget


class TestFrontierTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join("scratch", "test_trainer_work")
        self.trainer = FrontierTrainer(work_dir=self.temp_dir)

    def test_run_training_generates_report_and_artifacts(self):
        report: TrainingRunReport = self.trainer.run_training(
            base_model="qwen2.5-coder:1.5b",
            output_model="saleha-test-model",
            enable_dpo=True,
            enable_rlif=True,
        )
        self.assertTrue(report.run_id)
        self.assertEqual(report.target_model_name, "saleha-test-model")
        self.assertGreater(len(report.phases_completed), 3)
        self.assertGreater(report.total_sft_samples, 0)
        self.assertGreater(report.total_dpo_pairs, 0)
        self.assertLess(report.final_loss, report.initial_loss)
        self.assertTrue(os.path.exists(report.adapter_artifact_path))
        self.assertTrue(os.path.exists(report.gguf_path))
        self.assertTrue(report.deployed_to_local_runtime)

        # Benchmark verifications
        self.assertEqual(len(report.benchmarks), 6)
        for b in report.benchmarks:
            self.assertGreater(b.achieved_score, b.baseline_score)
            self.assertEqual(b.status, "TOP_TIER_PASS")
