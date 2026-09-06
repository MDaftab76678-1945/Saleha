"""Tests for Local LoRA Fine-Tuning Pipeline and Training Data Collector."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import unittest.mock
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
        # Real backend detection: either the local PEFT/TRL stack is
        # importable, or it isn't. There is no more fake "simulation" mode.
        backend = self.tuner._detect_backend()
        self.assertIn(backend, ["transformers_peft", "unavailable"])

    def test_insufficient_data_returns_error(self):
        result = self.tuner.fine_tune()
        self.assertFalse(result.success)
        self.assertIn("Insufficient", result.error)

    @unittest.skipUnless(
        os.environ.get("SALEHA_RUN_GPU_TESTS") == "1",
        "real LoRA SFT training run; set SALEHA_RUN_GPU_TESTS=1 to run it",
    )
    def test_real_training_with_enough_data(self):
        """Real end-to-end LoRA SFT on the smallest cached model (fast, no fake numbers)."""
        for i in range(6):
            self.tuner.collector.add_sample(
                f"Write a Python function that returns {i}.",
                f"def func_{i}():\n    return {i}",
                quality_score=0.9
            )
        cfg = TuningConfig(
            base_model="qwen2.5-coder:3b", epochs=1, batch_size=1,
            output_model_name="test_real_tune", deploy_to_ollama=False, run_benchmark=False,
        )
        result = self.tuner.fine_tune(cfg)
        self.assertTrue(result.success, result.error)
        self.assertGreater(result.samples_used, 0)
        self.assertIsInstance(result.before_score, float)
        self.assertIsInstance(result.after_score, float)
        self.assertTrue(os.path.exists(os.path.join(result.adapter_path, "adapter_model.safetensors")))

    @unittest.skipUnless(
        os.environ.get("SALEHA_RUN_GPU_TESTS") == "1",
        "real LoRA SFT training run; set SALEHA_RUN_GPU_TESTS=1 to run it",
    )
    def test_tuning_result_fields(self):
        for i in range(6):
            self.tuner.collector.add_sample(f"Write function returning {i}", f"def f(): return {i}", quality_score=0.9)
        cfg = TuningConfig(
            base_model="qwen2.5-coder:3b", epochs=1, batch_size=1,
            output_model_name="test_fields_tune", deploy_to_ollama=False, run_benchmark=False,
        )
        result = self.tuner.fine_tune(cfg)
        self.assertIsInstance(result.improvement_pct, float)
        self.assertIsInstance(result.training_time_sec, float)
        self.assertIsInstance(result.adapter_path, str)


class LlamaCppGgufFixTests(unittest.TestCase):
    """
    Real bug this fixes: `ollama create` importing directly from a raw HF
    safetensors directory was verified to silently produce degenerate
    output on this platform at every quantization level, even on
    returncode 0. Verified end-to-end (real merged model -> real
    convert_hf_to_gguf.py -> real Ollama import -> real generation, no
    degenerate output) that routing through a real llama.cpp checkout's
    converter first fixes this. These tests cover the discovery/fallback
    logic without needing GPU/network -- the full real conversion was
    verified manually, not re-run here on every test invocation.
    """

    def setUp(self):
        self._old_env = os.environ.get("SALEHA_LLAMA_CPP_DIR")

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("SALEHA_LLAMA_CPP_DIR", None)
        else:
            os.environ["SALEHA_LLAMA_CPP_DIR"] = self._old_env

    def test_no_checkout_configured_returns_none(self):
        """Neither the env var nor the ~/.saleha/llama.cpp default resolves
        -> None. Patches expanduser too, since this dev machine has a real
        checkout installed at the default path (that's the point of the
        fix) -- this test must still pass regardless of that."""
        from saleha.core.lora_tuner import _find_llama_cpp_converter
        tmp = tempfile.mkdtemp()
        try:
            os.environ["SALEHA_LLAMA_CPP_DIR"] = os.path.join(tmp, "does_not_exist")
            with unittest.mock.patch("os.path.expanduser", return_value=os.path.join(tmp, "fake_home")):
                self.assertIsNone(_find_llama_cpp_converter())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_env_var_checkout_is_discovered(self):
        from saleha.core.lora_tuner import _find_llama_cpp_converter
        tmp = tempfile.mkdtemp()
        try:
            script_path = os.path.join(tmp, "convert_hf_to_gguf.py")
            with open(script_path, "w") as f:
                f.write("# fake converter for test discovery only\n")
            os.environ["SALEHA_LLAMA_CPP_DIR"] = tmp
            self.assertEqual(_find_llama_cpp_converter(), script_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_conversion_failure_returns_none_not_exception(self):
        """A configured-but-broken converter must fail soft (None), so
        register_with_ollama() falls back to the direct-safetensors path
        instead of crashing the whole deployment."""
        from saleha.core.lora_tuner import _convert_to_gguf_via_llama_cpp
        tmp = tempfile.mkdtemp()
        try:
            broken_script = os.path.join(tmp, "convert_hf_to_gguf.py")
            with open(broken_script, "w") as f:
                f.write("import sys; sys.exit(1)\n")
            os.environ["SALEHA_LLAMA_CPP_DIR"] = tmp
            out = os.path.join(tmp, "out.gguf")
            result = _convert_to_gguf_via_llama_cpp(tmp, out)
            self.assertIsNone(result)
            self.assertFalse(os.path.exists(out))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

