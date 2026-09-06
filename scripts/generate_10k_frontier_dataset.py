"""
Saleha: High-Speed Frontier Dataset Generator (1,000 to 10,000+ SFT & DPO Pairs)

Executes multi-language synthesis across Python, TypeScript, Rust, Go, and SQL.
Produces:
1. datasets/saleha_dpo_pairs.jsonl (Direct Preference Optimization Pairs)
2. datasets/saleha_sft_10k.jsonl (ShareGPT Multi-Turn Format)
3. datasets/saleha_sft_10k_alpaca.json (Alpaca Instruction Format)
"""

import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from saleha.core.dpo_dataset_engine import SalehaDPODatasetEngine, dpo_dataset_engine


def main():
    target_count = 1000
    if len(sys.argv) > 1:
        try:
            target_count = int(sys.argv[1])
        except ValueError:
            target_count = 1000

    print(f"🚀 Initializing Saleha Frontier Dataset Synthesis (Target: {target_count}+ Polyglot Pairs)...")
    start_t = time.time()
    
    engine = SalehaDPODatasetEngine(output_dir="datasets")
    dpo_count, sft_count = engine.build_dataset(target_count=target_count)

    dpo_path = engine.export_dpo_jsonl()
    sft_path = engine.export_sft_jsonl()
    alpaca_path = engine.export_alpaca_json()

    elapsed = round(time.time() - start_t, 2)
    print("\n" + "=" * 65)
    print(f"✨ Polyglot Dataset Synthesis Completed in {elapsed}s!")
    print("=" * 65)
    print(f"  • Total DPO Preference Pairs : {dpo_count}")
    print(f"  • Total SFT Instruction Pairs: {sft_count}")
    print(f"  • DPO JSONL Export           : {dpo_path}")
    print(f"  • SFT ShareGPT Export        : {sft_path}")
    print(f"  • SFT Alpaca JSON Export     : {alpaca_path}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
