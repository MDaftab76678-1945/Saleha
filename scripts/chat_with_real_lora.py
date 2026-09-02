"""
Saleha: Real-Time Interactive Terminal Chat with Trained LoRA Model

Allows live multi-turn conversation with the real LoRA model on NVIDIA RTX 3050 GPU.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from rich.console import Console
from rich.panel import Panel
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer
from peft import PeftModel


def main():
    console = Console()
    console.print("\n" + "=" * 80, style="bold green")
    console.print("💬 [bold white on green] SALEHA REAL LoRA INTERACTIVE TERMINAL CHAT [/]", justify="center")
    console.print("=" * 80, style="bold green")
    console.print("[dim]Type your coding question or prompt. Type 'exit' or 'quit' to end session.[/dim]\n")

    base_model_id = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    adapter_path = os.path.abspath("models/saleha_full_real_master_adapter")
    if not os.path.exists(adapter_path):
        adapter_path = os.path.abspath("models/saleha_real_lora_adapter")

    console.print(f"📥 Loading Base Model & Merging LoRA Weights on [yellow]NVIDIA GPU[/]...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.eval()

    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    console.print("✅ [bold green]Model Ready for Live Conversations![/]\n")

    conversation_history = [
        {"role": "system", "content": "You are Saleha, an autonomous Neuro-Symbolic AI Coding Assistant."}
    ]

    while True:
        try:
            user_input = console.input("[bold cyan]User ❯ [/]").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n[bold yellow]👋 Exiting Saleha Real Chat. Goodbye![/]\n")
                break

            conversation_history.append({"role": "user", "content": user_input})
            text = tokenizer.apply_chat_template(conversation_history, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer([text], return_tensors="pt").to("cuda")

            console.print("\n[bold green]Saleha ❯[/] ", end="")
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    streamer=streamer,
                    max_new_tokens=512,
                    temperature=0.2,
                    top_p=0.9,
                    do_sample=True,
                )

            # Store assistant response in history
            new_tokens = outputs[0][len(inputs.input_ids[0]):]
            assistant_reply = tokenizer.decode(new_tokens, skip_special_tokens=True)
            conversation_history.append({"role": "assistant", "content": assistant_reply})
            console.print()

        except KeyboardInterrupt:
            console.print("\n[bold yellow]Session interrupted. Goodbye![/]\n")
            break


if __name__ == "__main__":
    main()
