"""
Saleha: DSA & LiveCodeBench Master Training Pipeline on NVIDIA RTX 3050 GPU
Trains Qwen2.5-Coder-3B-Instruct with 4-bit NF4 QLoRA on the cleaned DSA dataset:
- LRU & LFU Caches with strict O(1)
- Fenwick Trees & Segment Trees with Lazy Propagation
- Skip Lists & Disjoint Set Union
- Monotonic Deques
Target: 100% (6/6) Score on Artificial Analysis Benchmark Suite
"""

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from rich.console import Console
from rich.table import Table
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)


def train_dsa_champion():
    console = Console()
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("🏆 [bold white on blue] SALEHA-ASI: DSA & LIVECODEBENCH CHAMPION GPU TRAINING [/]", justify="center")
    console.print("=" * 80, style="bold cyan")

    if not torch.cuda.is_available():
        console.print("[bold red]CUDA Error: NVIDIA GPU not detected![/]")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    console.print(f"🎮 Target Hardware: [bold green]{gpu_name}[/] ({vram_gb} GB VRAM)")

    base_model_id = "Qwen/Qwen2.5-Coder-3B-Instruct"
    adapter_save_path = os.path.abspath("models/saleha_asi_master_adapter")

    dsa_file = "datasets/saleha_dsa_livecodebench_train.json"
    math_file = "datasets/saleha_asi_math_reasoning_train.json"

    console.print(f"📖 Ingesting Cleaned DSA Dataset: [bold yellow]{dsa_file}[/]...")
    raw_samples = []
    if os.path.exists(dsa_file):
        with open(dsa_file, "r", encoding="utf-8") as f:
            dsa_data = json.load(f)
            for item in dsa_data:
                raw_samples.append({
                    "instruction": item["instruction"],
                    "response": item["response"]
                })
        console.print(f"   + Loaded {len(dsa_data)} clean DSA samples")

    if os.path.exists(math_file):
        with open(math_file, "r", encoding="utf-8") as f:
            math_data = json.load(f)
            for item in math_data[:500]:
                raw_samples.append({
                    "instruction": item["instruction"],
                    "response": item.get("response") or item.get("output", "")
                })
        console.print(f"   + Blended 500 Mathematics & Reasoning samples (Total: {len(raw_samples)} samples)")

    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def formatting_prompts_func(example):
        text = (
            f"<|im_start|>system\nYou are Saleha-ASI, an autonomous Super-Intelligent Neuro-Symbolic AI Reasoning Engine.<|im_end|>\n"
            f"<|im_start|>user\n{example['instruction']}<|im_end|>\n"
            f"<|im_start|>assistant\n{example['response']}<|im_end|>"
        )
        tokens = tokenizer(text, truncation=True, max_length=1024, padding=False)
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    raw_dataset = Dataset.from_list(raw_samples)
    tokenized_dataset = raw_dataset.map(formatting_prompts_func, remove_columns=["instruction", "response"])

    console.print(f"📥 Loading Base Model: [bold cyan]{base_model_id}[/] (4-Bit NF4)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
    )

    base_model = prepare_model_for_kbit_training(base_model)

    peft_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(base_model, peft_config)
    trainable_params, all_param = model.get_nb_trainable_parameters()
    console.print(f"🧠 LoRA Trainable Parameters: [bold green]{trainable_params:,}[/] / {all_param:,} ({100 * trainable_params / all_param:.2f}%)")

    training_args = TrainingArguments(
        output_dir="./runs/saleha_dsa_champion",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        warmup_steps=10,
        num_train_epochs=1,
        learning_rate=2.5e-4,
        fp16=True,
        logging_steps=10,
        save_strategy="no",
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True),
    )

    console.print("\n🚀 [bold green]Starting DSA Champion GPU Training Run...[/]\n")
    start_time = time.time()
    train_result = trainer.train()
    training_duration = time.time() - start_time

    console.print(f"\n💾 Saving Refined DSA Master Adapter to: [bold cyan]{adapter_save_path}[/]...")
    model.save_pretrained(adapter_save_path)
    tokenizer.save_pretrained(adapter_save_path)

    table = Table(title="🏆 Saleha DSA Champion Training Summary", border_style="green")
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="cyan")
    table.add_row("Base Architecture", f"{base_model_id} (3.09B)")
    table.add_row("Dataset", f"{len(raw_samples)} High-Density Samples")
    table.add_row("Final Loss", f"{train_result.training_loss:.4f}")
    table.add_row("Runtime", f"{training_duration:.2f} seconds")
    table.add_row("Adapter Location", adapter_save_path)
    console.print(table)
    console.print("\n✨ [bold green]DSA & LIVECODEBENCH REFINEMENT COMPLETED WITH 100% SUCCESS![/]\n")


if __name__ == "__main__":
    train_dsa_champion()
