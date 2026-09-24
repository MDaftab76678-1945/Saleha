#!/usr/bin/env python3
"""
Saleha-Coder SLM Distillation Pipeline -- environment check.

This script does not train anything. It checks that the fine-tuning stack is
installed and exits non-zero when it is not. Real LoRA training is
saleha.core.lora_tuner.LoRATuner.
"""

import sys


def run_fine_tuning() -> int:
    print("Saleha-Coder SLM Distillation Pipeline: environment check (no training runs here)")
    print("Dataset : datasets/saleha_train_dataset.jsonl")
    print("Base    : Qwen/Qwen2.5-Coder-1.5B-Instruct, LoRA r=16 alpha=32")
    missing = []
    for mod in ("torch", "transformers", "peft", "trl", "datasets"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print("Missing: " + ", ".join(missing) + ". Install them before training.")
        return 1
    print("All dependencies import. Train with saleha.core.lora_tuner.LoRATuner.")
    return 0


if __name__ == "__main__":
    sys.exit(run_fine_tuning())
