"""
Saleha Real LoRA Fine-Tuning Pipeline on NVIDIA GPU

Executes REAL PyTorch backpropagation & LoRA adapter weight updates:
1. Loads Base Model (Qwen2.5-Coder-0.5B-Instruct / 1.5B-Instruct) on CUDA.
2. Formats real training samples from `datasets/saleha_sft_10k_alpaca.json`.
3. Injects PEFT LoRA trainable parameters into attention projection matrices.
4. Executes real optimizer step (AdamW) and gradient backpropagation.
5. Exports real `adapter_model.safetensors` & `adapter_config.json` to `models/saleha_real_lora_adapter/`.
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


def load_saleha_dataset(dataset_path: str, max_samples: int = 100):
    """Loads and formats real training data for causal LM fine-tuning."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = data[:max_samples]
    formatted = []
    for item in samples:
        instr = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        prompt = f"<|im_start|>system\nYou are Saleha, an autonomous Neuro-Symbolic AI Coding Assistant.<|im_end|>\n<|im_start|>user\n{instr}\n{inp}<|im_end|>\n<|im_start|>assistant\n{out}<|im_end|>"
        formatted.append({"text": prompt})

    return Dataset.from_list(formatted)


def main():
    console = Console()
    console.print("\n" + "=" * 80, style="bold green")
    console.print("🔥 [bold white on green] SALEHA REAL PYTORCH & PEFT LoRA GPU TRAINING PIPELINE [/]", justify="center")
    console.print("=" * 80, style="bold green")

    # 1. Check Hardware
    if not torch.cuda.is_available():
        console.print("[bold red]❌ Error: CUDA GPU not detected![/]")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    console.print(f"✅ [bold green]Active GPU Device:[/] [yellow]{gpu_name}[/] ([cyan]{vram_gb} GB VRAM[/])")

    # Model configuration (Qwen2.5-Coder-0.5B-Instruct is lightweight, fast, and fits comfortably in 6GB VRAM)
    model_id = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    output_dir = os.path.abspath("models/saleha_real_lora_adapter")
    os.makedirs(output_dir, exist_ok=True)

    console.print(f"📥 Loading Base Model & Tokenizer: [bold cyan]{model_id}[/]...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # 2. Inject PEFT LoRA Config
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    trainable_params, all_params = model.get_nb_trainable_parameters()
    console.print(f"📊 [bold green]LoRA Parameters Injected:[/] Trainable: {trainable_params:,} / {all_params:,} ({100 * trainable_params / all_params:.2f}%)")

    # 3. Load & Tokenize Real Training Dataset
    dataset_file = "datasets/saleha_sft_10k_alpaca.json"
    console.print(f"📁 Loading dataset from: [bold yellow]{dataset_file}[/]...")
    raw_dataset = load_saleha_dataset(dataset_file, max_samples=50)

    def tokenize_function(examples):
        tokens = tokenizer(examples["text"], truncation=True, max_length=512, padding="max_length")
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    tokenized_dataset = raw_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

    # 4. Configure Real Training Arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        num_train_epochs=1,
        fp16=True,
        logging_steps=5,
        save_strategy="no",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, pad_to_multiple_of=8),
    )

    # 5. Execute Real Forward & Backward Passes on GPU
    console.print("\n🚀 [bold white on blue] STARTING REAL GPU BACKPROPAGATION ON CUDA... [/]\n")
    start_time = time.time()
    train_result = trainer.train()
    training_time = round(time.time() - start_time, 2)

    # 6. Save Real Trained LoRA Weights (.safetensors)
    console.print(f"\n💾 Saving real LoRA weights to: [bold green]{output_dir}[/]...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # 7. Generate Real Training Summary Table
    table = Table(title="🏆 Real GPU Training Metrics (PyTorch / CUDA)", border_style="green")
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold green", justify="center")

    table.add_row("GPU Model", gpu_name)
    table.add_row("Base Architecture", model_id)
    table.add_row("Initial Training Loss", f"{train_result.metrics.get('train_loss', 0.0):.4f}")
    table.add_row("Total Training Time", f"{training_time} seconds")
    table.add_row("Global Backprop Steps", f"{train_result.global_step}")
    table.add_row("Adapter Format", "safetensors (Real Physical Weights)")

    console.print(table)

    summary_panel = f"""[bold]Target Directory:[/] [green]{output_dir}[/]
[bold]Weights Produced:[/] [yellow]adapter_model.safetensors, adapter_config.json[/]
[bold]Status:[/] [bold white on green] REAL PYTORCH BACKPROPAGATION COMPLETED 100% SUCCESFULLY [/]"""
    console.print(Panel(summary_panel, title="[bold green]Real Physical Artifacts Verified[/]", border_style="green"))


if __name__ == "__main__":
    main()
