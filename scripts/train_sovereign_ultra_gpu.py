"""
Saleha Sovereign Ultra Agentic Training Pipeline
Runs 4-bit NF4 QLoRA (bf16 compute) on an NVIDIA RTX 3050 Laptop GPU.
Trains completion-only loss over the consolidated Sovereign-Ultra dataset
using the Qwen2.5 ChatML prompt format (system + user + assistant).
"""

import json
import os
import sys
import time
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)
from transformers.trainer_utils import get_last_checkpoint

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_LEN = 1024
SYSTEM_PROMPT = "You are Saleha, a helpful, precise agentic super-intelligence assistant."


def build_turns(instruction, user_input, output):
    """Return (prompt_text, full_text) using the Qwen2.5 ChatML format.

    prompt_text is everything up to and including the assistant header, so we can
    mask it out of the loss and train on the completion only.
    """
    instruction = (instruction or "").strip()
    user_input = (user_input or "").strip()
    if user_input:
        user_content = f"{instruction}\n\nInput Context:\n{user_input}"
    else:
        user_content = instruction
    prompt_text = (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user_content}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    full_text = f"{prompt_text}{output.strip()}<|im_end|>"
    return prompt_text, full_text


def main():
    print("=" * 70)
    print("  👑 SALEHA SOVEREIGN ULTRA AGENTIC GPU TRAINING  ")
    print("=" * 70)

    dataset_path = os.path.abspath("datasets/saleha_sovereign_train.json")
    output_dir = os.path.abspath("models/saleha_asi_master_adapter")
    base_model_id = "Qwen/Qwen2.5-Coder-3B-Instruct"

    if not torch.cuda.is_available():
        print("❌ Error: CUDA-enabled GPU is required for training.")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"🎮 Target Hardware: {gpu_name} ({total_vram_gb:.2f} GB VRAM)")

    # 1. Load Dataset
    print(f"📦 Loading dataset from: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    print(f"📊 Total Training Samples: {len(raw_data)}")

    # 2. Tokenizer
    print("🔤 Loading Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 3. Format & Tokenize (completion-only loss, ChatML format)
    pairs = []
    dropped = 0
    for item in raw_data:
        output = item.get("output") or item.get("response")
        if not output:
            dropped += 1
            continue
        pairs.append(
            build_turns(
                item.get("instruction") or item.get("prompt", ""),
                item.get("input", ""),
                output,
            )
        )
    print(f"🧹 Usable samples: {len(pairs)} (dropped {dropped} with no output)")

    truncated = {"n": 0}

    def tokenize_fn(examples):
        input_ids_batch, labels_batch, attn_batch = [], [], []
        for prompt_text, full_text in zip(examples["prompt"], examples["full"]):
            full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
            prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
            if len(full_ids) > MAX_LEN:
                truncated["n"] += 1
                full_ids = full_ids[:MAX_LEN]
            n_prompt = min(len(prompt_ids), len(full_ids))
            labels = [-100] * n_prompt + full_ids[n_prompt:]
            input_ids_batch.append(full_ids)
            labels_batch.append(labels)
            attn_batch.append([1] * len(full_ids))
        return {
            "input_ids": input_ids_batch,
            "labels": labels_batch,
            "attention_mask": attn_batch,
        }

    hf_dataset = Dataset.from_dict(
        {"prompt": [p for p, _ in pairs], "full": [f for _, f in pairs]}
    )
    tokenized_dataset = hf_dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=["prompt", "full"],
        desc="Tokenizing samples",
    )
    print(
        f"✂️  Samples longer than {MAX_LEN} tokens (tail truncated): {truncated['n']}"
    )

    # 4. BitsAndBytes 4-bit Config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # 5. Load Base Model
    print(f"📥 Loading Base Model in 4-bit NF4: {base_model_id}...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
    )

    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True
    )
    model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )

    # 6. LoRA Configuration
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    trainable_params, all_params = model.get_nb_trainable_parameters()
    print(
        f"🧠 LoRA Trainable Parameters: {trainable_params:,} / {all_params:,} "
        f"({100 * trainable_params / all_params:.2f}%)"
    )

    # 7. Training Arguments (with checkpoint saving for power-outage safety)
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        warmup_steps=20,
        lr_scheduler_type="cosine",
        num_train_epochs=1,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        optim="paged_adamw_8bit",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True
        ),
    )

    # Auto-resume from last checkpoint if one exists
    resume_ckpt = None
    if os.path.isdir(output_dir):
        resume_ckpt = get_last_checkpoint(output_dir)
    if resume_ckpt:
        print(f"\n🔄 Resuming from checkpoint: {resume_ckpt}")
    else:
        print("\n🚀 Starting fresh Saleha Sovereign Ultra GPU Training Run...")

    t0 = time.time()
    train_result = trainer.train(resume_from_checkpoint=resume_ckpt)
    total_time = time.time() - t0

    # 8. Save LoRA Adapter
    print(f"\n💾 Saving Refined Sovereign-Ultra LoRA Adapter to: {output_dir}...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("\n" + "=" * 70)
    print("      👑 SALEHA SOVEREIGN ULTRA AGENTIC TRAINING COMPLETED!       ")
    print("=" * 70)
    print(f"Total Samples Trained : {len(raw_data)}")
    print(f"Final Training Loss   : {train_result.training_loss:.4f}")
    print(f"Total Runtime         : {total_time:.2f} seconds ({total_time/60:.1f} mins)")
    print(f"Saved LoRA Adapter    : {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
