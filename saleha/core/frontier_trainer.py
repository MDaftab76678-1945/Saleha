"""
Saleha Core: Frontier Model Trainer & Benchmark Alignment Engine

Orchestrates multi-phase local fine-tuning:

1. Phase 1 (SFT): real PEFT/TRL LoRA training, delegated to LoRATuner.
2. Phase 2 (DPO): real trl.DPOTrainer run, but ONLY when a real preference
   dataset (datasets/saleha_dpo_pairs.jsonl) with enough pairs exists --
   otherwise this phase is honestly reported as skipped, with the reason.
3. Phase 3 (RLIF -- reward/invariant-guided RL): NOT IMPLEMENTED. An earlier
   version of this module faked this phase (a `time.sleep()` "progress bar",
   a hand-written empty GGUF file with no tensors, and a hardcoded benchmark
   table where every score was "TOP_TIER_PASS"). Real RL-from-sandbox-
   execution-feedback is a substantial project on its own; this module
   reports the gap instead of inventing results for it.
4. Deployment + evaluation: delegated to LoRATuner.register_with_ollama()
   (real GGUF conversion via `ollama create`, not hand-rolled bytes) and
   saleha.core.evaluator.ModelBenchmarkEvaluator (real sandboxed Pass@1),
   not fabricated benchmark numbers.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List, Optional

from saleha.core.lora_tuner import LoRATuner, TuningConfig, TuningResult

DPO_PAIRS_PATH = os.path.join("datasets", "saleha_dpo_pairs.jsonl")
MIN_DPO_PAIRS = 20  # below this, a DPO pass is more noise than signal


@dataclass
class TrainingRunReport:
    run_id: str
    base_model: str
    target_model_name: str
    phases_completed: List[str]
    phases_skipped: List[str]
    sft_result: Optional[TuningResult]
    total_dpo_pairs: int
    dpo_final_loss: Optional[float]
    training_duration_sec: float
    adapter_artifact_path: str
    deployed_to_ollama: bool
    benchmark_before_pass_rate: Optional[float] = None
    benchmark_after_pass_rate: Optional[float] = None
    error: str = ""


class FrontierTrainer:
    """
    Multi-phase local fine-tuning orchestrator. Every phase either does real
    work or is honestly reported as skipped/unimplemented -- no fabricated
    metrics, no placeholder artifacts.
    """

    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = work_dir or os.path.expanduser("~/.saleha/frontier_training")
        os.makedirs(self.work_dir, exist_ok=True)
        self.tuner = LoRATuner(work_dir=os.path.join(self.work_dir, "lora"))

    def run_training(
        self,
        base_model: str = "qwen2.5-coder:3b",
        output_model: str = "saleha-frontier",
        epochs: int = 3,
        enable_dpo: bool = True,
        deploy_to_ollama: bool = True,
        run_benchmark: bool = True,
    ) -> TrainingRunReport:
        """Executes the real multi-phase training cycle."""
        start_t = time.time()
        run_id = f"run_{int(start_t)}"
        phases_completed: List[str] = []
        phases_skipped: List[str] = []

        # --- Phase 1: real SFT (delegated) ---
        sft_cfg = TuningConfig(
            base_model=base_model, output_model_name=output_model, epochs=epochs,
            deploy_to_ollama=deploy_to_ollama, run_benchmark=run_benchmark,
        )
        sft_result = self.tuner.fine_tune(sft_cfg)
        if sft_result.success:
            phases_completed.append("Phase 1: SFT (real PEFT/TRL LoRA training)")
        else:
            phases_skipped.append(f"Phase 1: SFT -- FAILED ({sft_result.error})")

        # --- Phase 2: DPO, only with a real preference dataset ---
        dpo_pairs = 0
        dpo_final_loss: Optional[float] = None
        if os.path.exists(DPO_PAIRS_PATH):
            with open(DPO_PAIRS_PATH, "r", encoding="utf-8") as f:
                dpo_pairs = sum(1 for line in f if line.strip())

        if not enable_dpo:
            phases_skipped.append("Phase 2: DPO -- SKIPPED (disabled by caller)")
        elif not sft_result.success:
            phases_skipped.append("Phase 2: DPO -- SKIPPED (Phase 1 did not succeed)")
        elif dpo_pairs < MIN_DPO_PAIRS:
            phases_skipped.append(
                f"Phase 2: DPO -- SKIPPED (found {dpo_pairs} preference pairs at "
                f"{DPO_PAIRS_PATH}, need >={MIN_DPO_PAIRS}; no fake pairs were substituted)"
            )
        else:
            try:
                dpo_final_loss = self._run_dpo(sft_result.adapter_path, base_model)
                phases_completed.append(f"Phase 2: DPO ({dpo_pairs} real preference pairs)")
            except Exception as e:
                phases_skipped.append(f"Phase 2: DPO -- FAILED ({e})")

        # --- Phase 3: RLIF -- honestly not implemented ---
        phases_skipped.append(
            "Phase 3: RLIF (MCTS/invariant-reward RL) -- NOT IMPLEMENTED. "
            "A prior version of this module fabricated this phase (fake sleep-based "
            "progress + hardcoded benchmark scores); it now reports the real gap "
            "instead of inventing results."
        )

        duration = round(time.time() - start_t, 2)
        return TrainingRunReport(
            run_id=run_id,
            base_model=base_model,
            target_model_name=output_model,
            phases_completed=phases_completed,
            phases_skipped=phases_skipped,
            sft_result=sft_result,
            total_dpo_pairs=dpo_pairs,
            dpo_final_loss=dpo_final_loss,
            training_duration_sec=duration,
            adapter_artifact_path=sft_result.adapter_path,
            deployed_to_ollama=sft_result.deployed_to_ollama,
            benchmark_before_pass_rate=sft_result.benchmark_before_pass_rate,
            benchmark_after_pass_rate=sft_result.benchmark_after_pass_rate,
            error=sft_result.error,
        )

    def _run_dpo(self, adapter_path: str, base_model: str) -> float:
        """Real DPO fine-tuning via trl.DPOTrainer, continuing from the SFT adapter."""
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        from saleha.core.lora_tuner import ensure_trl_dpo_importable
        ensure_trl_dpo_importable()
        from trl import DPOTrainer, DPOConfig

        hf_base = self.tuner._resolve_hf_base(base_model)
        tokenizer = AutoTokenizer.from_pretrained(hf_base)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        device = "cuda" if torch.cuda.is_available() else "cpu"
        base = AutoModelForCausalLM.from_pretrained(
            hf_base, dtype=torch.bfloat16 if device == "cuda" else torch.float32, device_map=device,
        )
        model = PeftModel.from_pretrained(base, adapter_path, is_trainable=True)

        dataset = load_dataset("json", data_files=DPO_PAIRS_PATH, split="train")

        dpo_config = DPOConfig(
            output_dir=os.path.join(self.work_dir, "dpo_run"),
            num_train_epochs=1,
            per_device_train_batch_size=1,
            learning_rate=5e-6,
            logging_steps=5,
            save_strategy="no",
            report_to=[],
        )
        trainer = DPOTrainer(model=model, args=dpo_config, train_dataset=dataset, processing_class=tokenizer)
        result = trainer.train()
        model.save_pretrained(adapter_path)  # overwrite SFT adapter with the DPO-aligned version
        return float(getattr(result, "training_loss", 0.0) or 0.0)


frontier_trainer = FrontierTrainer()
