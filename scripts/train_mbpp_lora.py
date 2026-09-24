"""Train a LoRA adapter for Qwen2.5-Coder-1.5B on MBPP's train split.

Data: MBPP "train" + "prompt" splits (reference solutions that pass their own
tests). "validation" and "test" are never trained on; scripts/mbpp_eval.py
measures the adapter on "test" against the base model.

    .venv_train/Scripts/python scripts/train_mbpp_lora.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mbpp_eval import BASE_MODEL, SYSTEM_PROMPT, load_mbpp, run_tests, user_prompt  # noqa: E402

MIN_TRAINING_SAMPLES = 20


def build_examples(tok: Any, max_len: int) -> List[Dict[str, List[int]]]:
    """Tokenised chat examples; loss is taken on the assistant reply only.

    A reference solution that fails its own tests is dropped, not trained on.
    """
    examples: List[Dict[str, List[int]]] = []
    dropped = 0
    for split in ("train", "prompt"):
        for task in load_mbpp(split):
            code = task["code"].replace("\r\n", "\n").strip()
            if not run_tests(code, task)["passed"]:
                dropped += 1
                continue
            prompt_msgs = [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": user_prompt(task)}]
            prompt_ids = tok.apply_chat_template(prompt_msgs, tokenize=True,
                                                 add_generation_prompt=True)
            if not isinstance(prompt_ids, list):
                prompt_ids = prompt_ids["input_ids"]
            reply_ids = tok(f"```python\n{code}\n```<|im_end|>\n",
                            add_special_tokens=False)["input_ids"]
            ids = (prompt_ids + reply_ids)[:max_len]
            labels = ([-100] * len(prompt_ids) + reply_ids)[:max_len]
            if all(label == -100 for label in labels):
                dropped += 1
                continue
            examples.append({"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels})
    print(f"training examples: {len(examples)} (dropped {dropped} whose reference failed or was cut)")
    return examples


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/saleha_mbpp_1.5b_lora")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=768)
    args = ap.parse_args()

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )

    from datasets import Dataset

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    examples = build_examples(tok, args.max_len)
    if len(examples) < MIN_TRAINING_SAMPLES:
        raise SystemExit(f"Refusing to train: {len(examples)} usable samples.")

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, device_map="cuda")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=args.rank, lora_alpha=args.rank * 2, lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    out = Path(args.out)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(out / "_checkpoints"), num_train_epochs=args.epochs,
            per_device_train_batch_size=2, gradient_accumulation_steps=8,
            learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=3,
            bf16=True, logging_steps=5, save_strategy="no", report_to=[], seed=0,
        ),
        train_dataset=Dataset.from_list(examples),
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
    )
    t0 = time.time()
    result = trainer.train()
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))

    saved = out / "adapter_model.safetensors"
    if not saved.is_file() or saved.stat().st_size == 0:
        raise SystemExit(f"Training ran but no adapter was written to {saved}")
    losses = [h["loss"] for h in trainer.state.log_history if "loss" in h]
    meta = {
        "base_model": BASE_MODEL, "examples": len(examples), "epochs": args.epochs,
        "lr": args.lr, "rank": args.rank, "train_loss": round(result.training_loss, 4),
        "first_logged_loss": losses[0] if losses else None,
        "last_logged_loss": losses[-1] if losses else None,
        "minutes": round((time.time() - t0) / 60, 1),
        "adapter_bytes": saved.stat().st_size,
    }
    (out / "training_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
