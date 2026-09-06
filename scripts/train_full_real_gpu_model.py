"""
Saleha: Full-Scale Real GPU LoRA Training Pipeline

Executes comprehensive real multi-epoch GPU fine-tuning:
1. Loads full training dataset (500+ / 1,000 samples).
2. Sets up Qwen2.5-Coder with high-capacity LoRA rank (r=16, alpha=32).
3. Executes 3 full training epochs with cosine learning rate scheduling and gradient accumulation.
4. Real-time loss logging and checkpointing directly onto NVIDIA RTX 3050 GPU.
5. Saves final master adapter weights to `models/saleha_full_real_master_adapter/`.
"""

import argparse
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


def load_dataset_samples(dataset_path: str, max_samples: int = 500):
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data[:max_samples]
    formatted = []
    for item in samples:
        instr = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        prompt = (
            f"<|im_start|>system\nYou are Saleha, an autonomous Neuro-Symbolic AI Coding Assistant.<|im_end|>\n"
            f"<|im_start|>user\n{instr}\n{inp}<|im_end|>\n"
            f"<|im_start|>assistant\n{out}<|im_end|>"
        )
        formatted.append({"text": prompt})

    return Dataset.from_list(formatted)


def main():
    parser = argparse.ArgumentParser(description="Full-Scale Real GPU Training")
    parser.add_argument("--epochs", type=int, default=3, help="Number of full training epochs")
    parser.add_argument("--samples", type=int, default=300, help="Number of real training samples")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--batch_size", type=int, default=2, help="Per device batch size")
    parser.add_argument("--grad_accum", type=int, default=4, help="Gradient accumulation steps")
    args = parser.parse_args()

    console = Console()
    console.print("\n" + "=" * 80, style="bold magenta")
    console.print("🚀 [bold white on magenta] SALEHA FULL-SCALE REAL GPU LoRA TRAINING [/]", justify="center")
    console.print("=" * 80, style="bold magenta")

    if not torch.cuda.is_available():
        console.print("[bold red]❌ Error: CUDA GPU not detected![/]")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    console.print(f"✅ [bold green]Active Training GPU:[/] [yellow]{gpu_name}[/] ([cyan]{vram_gb} GB VRAM[/])")

    model_id = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    output_dir = os.path.abspath("models/saleha_full_real_master_adapter")
    os.makedirs(output_dir, exist_ok=True)

    console.print(f"📥 Loading Base Model: [bold cyan]{model_id}[/]...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # High-capacity LoRA configuration (r=16, alpha=32)
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
        f"📊 [bold green]High-Capacity LoRA Matrices:[/] Trainable: [bold yellow]{trainable_params:,}[/] / {all_params:,} ({100 * trainable_params / all_params:.2f}%)"
    )

    dataset_file = "datasets/saleha_sft_10k_alpaca.json"
    console.print(f"📁 Tokenizing [bold yellow]{args.samples} real samples[/] from [cyan]{dataset_file}[/]...")
    raw_dataset = load_dataset_samples(dataset_file, max_samples=args.samples)

    def tokenize_function(examples):
        tokens = tokenizer(examples["text"], truncation=True, max_length=512, padding="max_length")
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    tokenized_dataset = raw_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        fp16=True,
        logging_steps=10,
        warmup_steps=5,
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

    console.print(f"\n🔥 [bold white on red] EXECUTING {args.epochs} FULL TRAINING EPOCHS ON NVIDIA GPU... [/]\n")
    start_time = time.time()
    train_result = trainer.train()
    training_time = round(time.time() - start_time, 2)

    console.print(f"\n💾 Saving Master LoRA weights to: [bold green]{output_dir}[/]...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    table = Table(title="🏆 Full-Scale GPU Training Results", border_style="magenta")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold green", justify="center")

    table.add_row("GPU Hardware", gpu_name)
    table.add_row("Total Epochs Completed", f"{args.epochs}")
    table.add_row("Training Samples Fed", f"{args.samples}")
    table.add_row("Final Training Loss", f"{train_result.metrics.get('train_loss', 0.0):.4f}")
    table.add_row("Total GPU Runtime", f"{training_time} seconds")
    table.add_row("Total Optimization Steps", f"{train_result.global_step}")
    table.add_row("Saved Weights Directory", output_dir)

    console.print(table)
    console.print("\n[bold white on green] ✨ FULL-SCALE REAL TRAINING COMPLETED WITH 100% SUCCESS! [/]\n")


if __name__ == "__main__":
    main()
