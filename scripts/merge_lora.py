"""
Saleha: Merge LoRA Adapter into Standalone Base Model
Produces consolidated weights in models/saleha_asi_merged for direct export to GGUF / Ollama.
"""

import os
import sys
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def merge_weights():
    base_model_id = "Qwen/Qwen2.5-Coder-3B-Instruct"
    adapter_path = os.path.abspath("models/saleha_asi_master_adapter")
    output_dir = os.path.abspath("models/saleha_asi_merged")

    print(f"📥 Loading Base Architecture: {base_model_id} in FP16 on CPU...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )

    print(f"🔌 Merging Rank-32 LoRA weights from {adapter_path}...")
    model = PeftModel.from_pretrained(base_model, adapter_path)
    merged_model = model.merge_and_unload()

    print(f"💾 Saving consolidated merged model to {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)
    merged_model.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)
    print("✅ Model successfully merged and saved ready for GGUF/Ollama conversion!")


if __name__ == "__main__":
    merge_weights()
