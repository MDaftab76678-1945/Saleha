"""Measure a local coder model on MBPP by running its code against the tests.

Ground truth is MBPP's own assert statements, executed in a subprocess -- the
model never sees whether it passed, and nothing here grades its own output.

    .venv_train/Scripts/python scripts/mbpp_eval.py                     # base model
    .venv_train/Scripts/python scripts/mbpp_eval.py --adapter models/x  # base + LoRA
    .venv_train/Scripts/python scripts/mbpp_eval.py --limit 20          # smoke run

Generated code runs locally with a timeout, in a throwaway directory. It is
model output: run this only on a machine where that is acceptable.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
SYSTEM_PROMPT = "You are a careful Python programmer. Reply with one ```python code block only."
_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def load_mbpp(split: str) -> List[Dict[str, Any]]:
    from datasets import load_dataset
    return list(load_dataset("google-research-datasets/mbpp", "full")[split])


def user_prompt(task: Dict[str, Any]) -> str:
    tests = "\n".join(task["test_list"])
    return f"{task['text']}\nYour code should pass these tests:\n\n{tests}"


def extract_code(reply: str) -> str:
    """The first fenced block, or the whole reply when the model used no fence."""
    match = _CODE_BLOCK.search(reply)
    return (match.group(1) if match else reply).strip()


def run_tests(code: str, task: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    """Runs the candidate plus MBPP's asserts; passed only if every assert ran.

    The marker prints after the last assert, so a candidate that calls
    sys.exit(0) or os._exit(0) before the tests cannot score as a pass.
    """
    marker = "__MBPP_ALL_ASSERTS_RAN__"
    program = "\n".join([
        code,
        task.get("test_setup_code") or "",
        *task["test_list"],
        f"print({marker!r})",
    ])
    if not code.strip():
        return {"passed": False, "reason": "empty code"}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(program, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(path)], cwd=tmp, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"passed": False, "reason": f"timeout after {timeout}s"}
    passed = proc.returncode == 0 and marker in proc.stdout
    reason = "" if passed else (proc.stderr.strip().splitlines() or [f"exit {proc.returncode}"])[-1]
    return {"passed": passed, "reason": reason[:300]}


def load_model(adapter: Optional[str]) -> Any:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, device_map="cuda")
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return tok, model


def generate(tok: Any, model: Any, prompts: List[str], max_new_tokens: int) -> List[str]:
    import torch

    texts = [
        tok.apply_chat_template(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": p}],
            tokenize=False, add_generation_prompt=True,
        )
        for p in prompts
    ]
    batch = tok(texts, return_tensors="pt", padding=True).to(model.device)
    with torch.no_grad():
        out = model.generate(**batch, max_new_tokens=max_new_tokens, do_sample=False,
                             pad_token_id=tok.pad_token_id)
    return tok.batch_decode(out[:, batch["input_ids"].shape[1]:], skip_special_tokens=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=None, help="LoRA adapter directory (default: base model)")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-new-tokens", type=int, default=384)
    ap.add_argument("--out", default=None, help="write per-task results as JSON here")
    args = ap.parse_args()

    tasks = load_mbpp(args.split)
    if args.limit:
        tasks = tasks[: args.limit]
    tok, model = load_model(args.adapter)

    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for i in range(0, len(tasks), args.batch):
        chunk = tasks[i: i + args.batch]
        replies = generate(tok, model, [user_prompt(t) for t in chunk], args.max_new_tokens)
        for task, reply in zip(chunk, replies, strict=True):
            verdict = run_tests(extract_code(reply), task)
            results.append({"task_id": task["task_id"], **verdict, "reply": reply})
        done = len(results)
        print(f"{done}/{len(tasks)} passed so far: {sum(r['passed'] for r in results)}", flush=True)

    passed = sum(r["passed"] for r in results)
    summary = {
        "model": BASE_MODEL, "adapter": args.adapter, "split": args.split,
        "passed": passed, "total": len(results),
        "pass_rate": round(passed / len(results), 4) if results else None,
        "minutes": round((time.time() - t0) / 60, 1),
    }
    print(json.dumps(summary))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "results": results}, indent=1),
                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
