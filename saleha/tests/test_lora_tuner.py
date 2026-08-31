"""Tests for Local LoRA Fine-Tuning Pipeline and Training Data Collector."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from saleha.core.training_collector import TrainingCollector, TrainingSample
from saleha.core.lora_tuner import LoRATuner, TuningConfig


class TrainingCollectorTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.collector = TrainingCollector(dataset_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_load_sample(self):
        self.collector.add_sample(
            prompt="Write a Python function to reverse a string",
            completion="def reverse(s): return s[::-1]",
            quality_score=0.9,
            source="manual",
            tags=["python", "strings"]
        )
        samples = self.collector.load_samples(min_quality=0.0)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].source, "manual")
        self.assertAlmostEqual(samples[0].quality_score, 0.9)

    def test_quality_filter(self):
        self.collector.add_sample("prompt1", "completion1", quality_score=0.5)
        self.collector.add_sample("prompt2", "completion2", quality_score=0.9)
        high = self.collector.load_samples(min_quality=0.8)
        self.assertEqual(len(high), 1)

    def test_source_filter(self):
        self.collector.add_sample("p1", "c1", source="session")
        self.collector.add_sample("p2", "c2", source="manual")
        session_samples = self.collector.load_samples(min_quality=0.0, source_filter="session")
        self.assertEqual(len(session_samples), 1)
        self.assertEqual(session_samples[0].source, "session")

    def test_export_alpaca_format(self):
        self.collector.add_sample("Question", "Answer", quality_score=0.8)
        out = os.path.join(self.tmp, "alpaca.json")
        count = self.collector.export_alpaca(out, min_quality=0.0)
        self.assertEqual(count, 1)
        with open(out) as f:
            data = json.load(f)
        self.assertIn("instruction", data[0])
        self.assertIn("output", data[0])
        self.assertEqual(data[0]["instruction"], "Question")

    def test_export_sharegpt_format(self):
        self.collector.add_sample("Human query", "AI response", quality_score=0.8)
        out = os.path.join(self.tmp, "sharegpt.jsonl")
        count = self.collector.export_sharegpt(out, min_quality=0.0)
        self.assertEqual(count, 1)
        with open(out) as f:
            data = json.loads(f.readline())
        self.assertIn("conversations", data)
        self.assertEqual(data["conversations"][0]["from"], "human")

    def test_stats_structure(self):
        self.collector.add_sample("p", "c", quality_score=0.9, source="session")
        stats = self.collector.stats()
        self.assertEqual(stats["total"], 1)
        self.assertIn("session", stats["sources"])
        self.assertGreater(stats["avg_quality"], 0.0)

    def test_sample_to_alpaca(self):
        s = TrainingSample(
            sample_id="x", prompt="do this", completion="done",
            quality_score=1.0, source="manual", tags=[], timestamp=""
        )
        alpaca = s.to_alpaca()
        self.assertEqual(alpaca["instruction"], "do this")
        self.assertEqual(alpaca["output"], "done")
        sgpt = s.to_sharegpt()
        self.assertIn("conversations", sgpt)


class LoRATunerTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tuner = LoRATuner(work_dir=self.tmp)
        self.tuner.collector = TrainingCollector(dataset_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detect_backend_returns_string(self):
        backend = self.tuner._detect_backend()
        self.assertIn(backend, ["unsloth", "llama.cpp", "simulation"])

    def test_insufficient_data_returns_error(self):
        result = self.tuner.fine_tune()
        self.assertFalse(result.success)
        self.assertIn("Insufficient", result.error)

    def test_simulation_mode_with_enough_data(self):
        for i in range(6):
            self.tuner.collector.add_sample(
                f"Task {i}: write function",
                f"def func_{i}(): return {i}",
                quality_score=0.9
            )
        import unittest.mock as mock
        with mock.patch.object(self.tuner, '_detect_backend', return_value='simulation'):
            result = self.tuner.fine_tune(TuningConfig())
        self.assertTrue(result.success)
        self.assertGreater(result.samples_used, 0)
        self.assertGreater(result.after_score, result.before_score)

    def test_tuning_result_fields(self):
        for i in range(6):
            self.tuner.collector.add_sample(f"p{i}", f"c{i}", quality_score=0.9)
        import unittest.mock as mock
        with mock.patch.object(self.tuner, '_detect_backend', return_value='simulation'):
            result = self.tuner.fine_tune()
        self.assertIsInstance(result.improvement_pct, float)
        self.assertIsInstance(result.training_time_sec, float)
        self.assertIsInstance(result.adapter_path, str)


if __name__ == "__main__":
    unittest.main()
