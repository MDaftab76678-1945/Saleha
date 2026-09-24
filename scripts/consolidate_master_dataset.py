"""
Saleha: merges the per-domain training files into
datasets/saleha_omni_grandmaster_train.json.

The output holds exactly what the inputs hold. Three of the four inputs are
empty (their earlier contents were purged as fabricated), so the output is
currently the DSA file's rows alone. Each input's row count is printed.
"""

import json
import os
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def consolidate():
    files = [
        ("datasets/saleha_dsa_livecodebench_train.json", "DSA LiveCodeBench"),
        ("datasets/saleha_asi_math_reasoning_train.json", "ASI Mathematics & CoT"),
        ("datasets/saleha_omni_hardcore_train.json", "Hardcore SWE & SSML"),
        ("datasets/saleha_artificial_analysis_omni_train.json", "Artificial Analysis Multi-Arena"),
    ]

    master_samples = []

    for path, label in files:
        if not os.path.exists(path):
            print(f"Warning: {path} not found, skipping.")
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            count = 0
            for item in data:
                instr = item.get("instruction") or item.get("prompt")
                resp = item.get("response") or item.get("output") or item.get("completion")
                if instr and resp:
                    master_samples.append({
                        "instruction": instr.strip(),
                        "response": resp.strip()
                    })
                    count += 1
            note = "  <-- EMPTY" if count == 0 else ""
            print(f"Ingested {count} samples from {label} ({path}){note}")

    random.seed(42)
    random.shuffle(master_samples)

    out_file = "datasets/saleha_omni_grandmaster_train.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(master_samples, f, indent=2)

    print(f"\nWrote {len(master_samples)} samples to '{out_file}'.")

if __name__ == "__main__":
    consolidate()
