"""
Saleha: exports the curated DPO / SFT dataset.

Writes the hand-written pairs from saleha/core/training/dpo_dataset_engine.py to:
1. datasets/saleha_dpo_pairs.jsonl (DPO pairs)
2. datasets/saleha_sft_10k.jsonl (ShareGPT format)
3. datasets/saleha_sft_10k_alpaca.json (Alpaca format)

The "10k" in the file names is historical: the files hold exactly the curated
pairs, however many exist. An optional argument caps the count; nothing pads it.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from saleha.core.training.dpo_dataset_engine import MIN_DPO_PAIRS, SalehaDPODatasetEngine  # noqa: E402


def main() -> int:
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else None
    engine = SalehaDPODatasetEngine(output_dir="datasets")
    dpo_count, sft_count = engine.build_dataset(target_count=cap)
    print(f"DPO pairs : {dpo_count} -> {engine.export_dpo_jsonl()}")
    print(f"SFT rows  : {sft_count} -> {engine.export_sft_jsonl()}")
    print(f"Alpaca    : {sft_count} -> {engine.export_alpaca_json()}")
    if dpo_count < MIN_DPO_PAIRS:
        print(f"Note: {dpo_count} pairs is below the {MIN_DPO_PAIRS} a DPO run needs; "
              "training will refuse until more real pairs are written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
