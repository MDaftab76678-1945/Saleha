"""
Saleha: Real 1.5B Parameter GPU LoRA Training Pipeline

Scales up to `Qwen/Qwen2.5-Coder-1.5B-Instruct` on NVIDIA GeForce RTX 3050 (6GB VRAM):
- 3x Parameter Reasoning Capacity (1.54 Billion Base Parameters)
- FP16 Mixed Precision with Gradient Checkpointing
- Invariant LoRA Rank=16, Alpha=32 across all projection matrices
- 500 High-Density Multi-Arena Samples
- Saves to `models/saleha_1.5b_master_adapter/`
"""

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from datasets import Dataset
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
)


def load_dataset(dataset_paths: list[str]):
    all_samples = []
    for path in dataset_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_samples.extend(data)

    formatted = []
    for item in all_samples:
        instr = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        prompt = (
            f"<|im_start|>system\nYou are Saleha-1.5B Pro, an autonomous Neuro-Symbolic AI Coding Assistant.<|im_end|>\n"
            f"<|im_start|>user\n{instr}\n{inp}<|im_end|>\n"
            f"<|im_start|>assistant\n{out}<|im_end|>"
        )
        formatted.append({"text": prompt})

    return Dataset.from_list(formatted)


def main():
    console = Console()
    console.print("\n" + "=" * 80, style="bold yellow")
    console.print("👑 [bold white on yellow] SALEHA-1.5B PRO REAL GPU TRAINING PIPELINE [/]", justify="center")
    console.print("=" * 80, style="bold yellow")
    console.print("[dim]Scaling from 0.5B to 1.54B Base Model on NVIDIA GeForce RTX 3050 GPU[/dim]\n")

    if not torch.cuda.is_available():
        console.print("[bold red]❌ Error: CUDA GPU not detected![/]")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    console.print(f"✅ [bold green]Active GPU:[/] [yellow]{gpu_name}[/] ([cyan]{vram_gb} GB VRAM[/])")

    model_id = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    output_dir = os.path.abspath("models/saleha_1.5b_master_adapter")
    os.makedirs(output_dir, exist_ok=True)

    console.print(f"📥 Loading 1.5B Base Architecture: [bold cyan]{model_id}[/]...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # Enable gradient checkpointing for optimal 6GB VRAM memory efficiency
    model.gradient_checkpointing_enable()

    # LoRA Config for 1.5B Model
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    trainable_params, all_params = model.get_nb_trainable_parameters()
    console.print(
        f"📊 [bold green]1.5B LoRA Parameters Injected:[/] Trainable: [bold yellow]{trainable_params:,}[/] / {all_params:,} ({100 * trainable_params / all_params:.2f}%)"
    )

    dataset_files = [
        "datasets/saleha_omni_hardcore_train.json",
        "datasets/saleha_artificial_analysis_omni_train.json",
    ]
    console.print(f"📁 Combining datasets: [cyan]{dataset_files}[/]...")
    raw_dataset = load_dataset(dataset_files)
    console.print(f"✅ Total formatted samples: [bold green]{len(raw_dataset)}[/]")

    def tokenize_function(examples):
        tokens = tokenizer(examples["text"], truncation=True, max_length=512, padding="max_length")
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    tokenized_dataset = raw_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

    # Training arguments optimized for 1.5B on 6GB VRAM
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        num_train_epochs=2,
        fp16=True,
        logging_steps=10,
        warmup_steps=5,
        max_grad_norm=0.5,
        lr_scheduler_type="cosine",
        save_strategy="no",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, pad_to_multiple_of=8),
    )

    console.print(f"\n🔥 [bold white on yellow] STARTING 1.5B PARAMETER REAL GPU TRAINING ON CUDA... [/]\n")
    start_time = time.time()
    train_result = trainer.train()
    training_time = round(time.time() - start_time, 2)

    console.print(f"\n💾 Saving 1.5B Master LoRA to: [bold green]{output_dir}[/]...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    table = Table(title="🏆 Saleha-1.5B Pro GPU Training Summary", border_style="yellow")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold green", justify="center")

    table.add_row("Base Architecture", "Qwen2.5-Coder-1.5B-Instruct (1.54B Params)")
    table.add_row("GPU Hardware", f"{gpu_name} (6.0 GB VRAM)")
    table.add_row("Total Samples Fed", f"{len(raw_dataset)} Multi-Arena Samples")
    table.add_row("Final Loss", f"{train_result.metrics.get('train_loss', 0.0):.4f}")
    table.add_row("Total GPU Runtime", f"{training_time} seconds")
    table.add_row("Adapter Location", output_dir)

    console.print(table)
    console.print("\n[bold white on green] ✨ 1.5B PRO REAL TRAINING COMPLETED WITH 100% SUCCESS! [/]\n")


if __name__ == "__main__":
    main()
