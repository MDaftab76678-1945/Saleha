#!/usr/bin/env python3
"""
Saleha-Coder LoRA / QLoRA fine-tuning script (HuggingFace TRL + PEFT).

Reads configs/lora_training_config.yaml and trains on the dataset it names.
It does not simulate anything: if the config, the dataset or a dependency is
missing it exits non-zero and says which one. Needs trl>=0.12, and a CUDA GPU
when load_in_4bit is true.
"""

import argparse
import json
import os
import sys

DEFAULT_CONFIG = "configs/lora_training_config.yaml"


def fail(reason):
    print("FAILED: " + reason, file=sys.stderr)
    return 1


def run_fine_tuning(config_path=DEFAULT_CONFIG):
    try:
        import yaml
    except ImportError:
        return fail("PyYAML is not installed (pip install pyyaml)")
    if not os.path.isfile(config_path):
        return fail("config not found: " + config_path)
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    dataset_path = cfg["dataset_path"]
    if not os.path.isfile(dataset_path):
        return fail("dataset not found: %s (create it with the /dataset command)" % dataset_path)
    with open(dataset_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows or "messages" not in rows[0]:
        return fail("%s must be chatml JSONL with a 'messages' field per line" % dataset_path)

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig
        from transformers import BitsAndBytesConfig
        from trl import SFTConfig, SFTTrainer
    except ImportError as exc:
        return fail("missing dependency (%s). Install: pip install torch transformers peft trl datasets bitsandbytes accelerate" % exc)

    init_kwargs = {}
    if cfg.get("load_in_4bit"):
        if not torch.cuda.is_available():
            return fail("load_in_4bit needs a CUDA GPU; none is available. Set load_in_4bit: false to train on CPU (very slow).")
        init_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=cfg.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_compute_dtype=getattr(torch, cfg.get("bnb_4bit_compute_dtype", "bfloat16")),
        )

    lora = LoraConfig(
        r=cfg["lora_r"],
        lora_alpha=cfg["lora_alpha"],
        lora_dropout=cfg["lora_dropout"],
        target_modules=cfg["target_modules"],
        task_type="CAUSAL_LM",
    )
    args = SFTConfig(
        output_dir=cfg["output_dir"],
        learning_rate=cfg["learning_rate"],
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["gradient_accumulation_steps"],
        num_train_epochs=cfg["num_train_epochs"],
        warmup_ratio=cfg["warmup_ratio"],
        lr_scheduler_type=cfg["lr_scheduler_type"],
        logging_steps=cfg["logging_steps"],
        save_strategy=cfg["save_strategy"],
        bf16=cfg.get("bf16", False),
        fp16=cfg.get("fp16", False),
        model_init_kwargs=init_kwargs or None,
    )
    dataset = load_dataset("json", data_files=dataset_path, split="train")
    print("Training %s on %d rows from %s" % (cfg["model_name_or_path"], len(dataset), dataset_path))

    trainer = SFTTrainer(model=cfg["model_name_or_path"], args=args, train_dataset=dataset, peft_config=lora)
    result = trainer.train()
    trainer.save_model(cfg["output_dir"])
    print("Done. train_loss=%s adapter saved to %s" % (result.training_loss, cfg["output_dir"]))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    sys.exit(run_fine_tuning(parser.parse_args().config))
