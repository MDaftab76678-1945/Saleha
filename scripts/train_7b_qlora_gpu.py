"""
Saleha: Real 7B (6B-Tier) Parameter 4-bit QLoRA GPU Training Pipeline

Executes 4-bit NormalFloat Quantized LoRA training for `Qwen/Qwen2.5-Coder-7B-Instruct`
on NVIDIA GeForce RTX 3050 (6.0 GB VRAM):
- Base Architecture: 7.61 Billion Parameters
- 4-Bit NF4 Quantization with Double Quantization (Fits inside ~4.2 GB VRAM)
- Paged AdamW 8-bit Optimizer
- Gradient Checkpointing
- High-Density Multi-Arena Leaderboard Datasets
- Saves to `models/saleha_7b_master_adapter/`
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
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
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
            f"<|im_start|>system\nYou are Saleha-7B Ultra, an autonomous enterprise-grade Neuro-Symbolic AI Coding Assistant.<|im_end|>\n"
            f"<|im_start|>user\n{instr}\n{inp}<|im_end|>\n"
            f"<|im_start|>assistant\n{out}<|im_end|>"
        )
        formatted.append({"text": prompt})

    return Dataset.from_list(formatted)


def main():
    console = Console()
    console.print("\n" + "=" * 80, style="bold magenta")
    console.print("🚀 [bold white on magenta] SALEHA-7B ULTRA REAL 4-BIT QLoRA TRAINING PIPELINE [/]", justify="center")
    console.print("=" * 80, style="bold magenta")
    console.print("[dim]Training 7.61 Billion Base Parameters on NVIDIA GeForce RTX 3050 (6GB VRAM)[/dim]\n")

    if not torch.cuda.is_available():
        console.print("[bold red]❌ Error: CUDA GPU not detected![/]")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    console.print(f"✅ [bold green]Active GPU:[/] [yellow]{gpu_name}[/] ([cyan]{vram_gb} GB VRAM[/])")

    model_id = "Qwen/Qwen2.5-Coder-7B-Instruct"
    output_dir = os.path.abspath("models/saleha_7b_master_adapter")
    os.makedirs(output_dir, exist_ok=True)

    console.print(f"📥 Loading 7B Base Architecture with NF4 Quantization: [bold cyan]{model_id}[/]...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 4-Bit NormalFloat Quantization Config (Double Quantization + CPU Offload)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )

    max_memory = {0: "5.5GB", "cpu": "24GB"}

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        max_memory=max_memory,
        trust_remote_code=True,
    )

    # Prepare model for k-bit training and enable gradient checkpointing
    model = prepare_model_for_kbit_training(model)

    # LoRA Config for 7B Architecture
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
        f"📊 [bold green]7B LoRA Parameters Injected:[/] Trainable: [bold yellow]{trainable_params:,}[/] / {all_params:,} ({100 * trainable_params / all_params:.2f}%)"
    )

    dataset_files = [
        "datasets/saleha_omni_hardcore_train.json",
        "datasets/saleha_artificial_analysis_omni_train.json",
    ]
    console.print(f"📁 Loading datasets: [cyan]{dataset_files}[/]...")
    raw_dataset = load_dataset(dataset_files)
    console.print(f"✅ Total formatted samples: [bold green]{len(raw_dataset)}[/]")

    def tokenize_function(examples):
        tokens = tokenizer(examples["text"], truncation=True, max_length=512, padding="max_length")
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    tokenized_dataset = raw_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

    # 4-bit QLoRA Training Arguments on 6GB VRAM
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        num_train_epochs=1,
        fp16=True,
        optim="paged_adamw_8bit",
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

    console.print(f"\n🔥 [bold white on magenta] STARTING 7B PARAMETER REAL 4-BIT QLoRA GPU TRAINING ON CUDA... [/]\n")
    start_time = time.time()
    train_result = trainer.train()
    training_time = round(time.time() - start_time, 2)

    console.print(f"\n💾 Saving 7B Master LoRA to: [bold green]{output_dir}[/]...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    table = Table(title="🏆 Saleha-7B Ultra QLoRA Training Summary", border_style="magenta")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold green", justify="center")

    table.add_row("Base Architecture", "Qwen2.5-Coder-7B-Instruct (7.61B Params)")
    table.add_row("Quantization Scheme", "4-Bit NF4 (Double Quantization)")
    table.add_row("GPU Hardware", f"{gpu_name} (6.0 GB VRAM)")
    table.add_row("Total Samples Fed", f"{len(raw_dataset)} Multi-Arena Samples")
    table.add_row("Final Loss", f"{train_result.metrics.get('train_loss', 0.0):.4f}")
    table.add_row("Total GPU Runtime", f"{training_time} seconds")
    table.add_row("Adapter Location", output_dir)

    console.print(table)
    console.print("\n[bold white on green] ✨ 7B ULTRA REAL QLoRA TRAINING COMPLETED WITH 100% SUCCESS! [/]\n")


if __name__ == "__main__":
    main()
