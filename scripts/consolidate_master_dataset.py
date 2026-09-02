"""
Saleha: Omni Grandmaster Dataset Consolidator (2,750 Master Samples)
Merges all specialized domains into a single unified training corpus:
1. DSA & LiveCodeBench (500 samples: LRU, LFU, Fenwick Trees, Skip Lists, O(1) algorithms)
2. ASI & Olympiad Mathematics (1,000 samples: Quadratic Reciprocity, Tonelli-Shanks, Byzantine CoT)
3. Hardcore Multi-Arena (500 samples: SWE-bench Git diffs, SSML audio tags, CUDA NVENC pipelines)
4. Pro Systems Architecture (750 samples: Distributed engines, high-concurrency protocols)
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
            print(f"⚠️ Warning: {path} not found, skipping.")
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
            print(f"✅ Ingested {count} samples from {label} ({path})")

    random.seed(42)
    random.shuffle(master_samples)

    out_file = "datasets/saleha_omni_grandmaster_train.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(master_samples, f, indent=2)

    print(f"\n🎉 Successfully consolidated {len(master_samples)} balanced master samples into '{out_file}'!")

if __name__ == "__main__":
    consolidate()
