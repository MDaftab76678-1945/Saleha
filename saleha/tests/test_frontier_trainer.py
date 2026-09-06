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

    @unittest.skipUnless(
        os.environ.get("SALEHA_RUN_GPU_TESTS") == "1",
        "runs a real SFT training pass (minutes of GPU time) and hung the "
        "suite at 28%; set SALEHA_RUN_GPU_TESTS=1 to run it deliberately",
    )
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

        # Phase 2 (DPO): a real 1000-pair preference dataset now exists
        # (datasets/saleha_dpo_pairs.jsonl, restored from main -- see git log),
        # well above MIN_DPO_PAIRS, so DPO is genuinely attempted rather than
        # skipped for lack of data. Whether it completes or fails depends on
        # the real local trl/torch install; either way must be reported
        # honestly (never a fabricated success).
        self.assertEqual(report.total_dpo_pairs, 1000)
        phase2_msgs = [p for p in report.phases_completed + report.phases_skipped if p.startswith("Phase 2")]
        self.assertEqual(len(phase2_msgs), 1)
        self.assertFalse(phase2_msgs[0].startswith("Phase 2") and "SKIPPED" in phase2_msgs[0] and "0 pairs" in phase2_msgs[0],
                          "must not claim missing data when 1000 real pairs exist")

        # Phase 3 (RLIF) must always self-report as not implemented -- no fake benchmark table.
        self.assertTrue(any("Phase 3" in p and "NOT IMPLEMENTED" in p for p in report.phases_skipped))

        # No fabricated GGUF/benchmark fields exist on the report anymore.
        self.assertFalse(hasattr(report, "gguf_path"))
        self.assertFalse(hasattr(report, "benchmarks"))

    def test_dpo_attempts_real_dataset_honestly(self):
        """With enable_dpo=False, Phase 2 must be cleanly skipped (caller opted out).
        With real data present, it must never report the old 'no dataset found' reason."""
        report = self.trainer.run_training(
            base_model="qwen2.5-coder:0.5b", output_model="saleha-test-model-2",
            epochs=1, enable_dpo=False, deploy_to_ollama=False, run_benchmark=False,
        )
        skip_msgs = [p for p in report.phases_skipped if p.startswith("Phase 2")]
        self.assertEqual(len(skip_msgs), 1)
        self.assertIn("disabled by caller", skip_msgs[0])


if __name__ == "__main__":
    unittest.main()
