"""
Saleha: Real LoRA Model Inference & Code Generation

Loads the REAL trained LoRA weights (adapter_model.safetensors) on NVIDIA RTX 3050 GPU
and generates code live!
"""

import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from rich.console import Console
from rich.panel import Panel
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


def main():
    console = Console()
    console.print("\n" + "=" * 80, style="bold green")
    console.print("🤖 [bold white on green] REAL INFERENCE WITH TRAINED SALEHA LoRA WEIGHTS [/]", justify="center")
    console.print("=" * 80, style="bold green")

    base_model_id = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    adapter_path = os.path.abspath("models/saleha_real_lora_adapter")

    console.print(f"📥 Loading Base Model: [bold cyan]{base_model_id}[/] on [yellow]NVIDIA GPU[/]...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    console.print(f"🔌 Merging Real LoRA Adapter: [bold yellow]{adapter_path}[/]...")
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()

    prompt = "Write a Python function to find all prime numbers up to n using the Sieve of Eratosthenes."
    console.print(f"\n💬 [bold yellow]User Prompt:[/] [white]{prompt}[/]\n")

    messages = [
        {"role": "system", "content": "You are Saleha, an autonomous Neuro-Symbolic AI Coding Assistant."},
        {"role": "user", "content": prompt},
    ]

    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to("cuda")

    console.print("⚡ Generating output live on NVIDIA RTX 3050 GPU...")
    start_t = time.perf_counter()
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.2,
            top_p=0.9,
            do_sample=True,
        )
    gen_time = round(time.perf_counter() - start_t, 2)

    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, generated_ids)
    ]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    tok_count = len(generated_ids[0])
    tok_per_sec = round(tok_count / gen_time, 2) if gen_time > 0 else 0

    console.print(Panel(response, title="[bold green]Real Model Generated Output[/]", border_style="green"))
    console.print(f"📊 [dim]Tokens Generated: {tok_count} | Latency: {gen_time}s | Speed: {tok_per_sec} tok/s on CUDA[/dim]\n")


if __name__ == "__main__":
    main()
