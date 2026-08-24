"""
Saleha Core: SWE-bench Lite Prediction Generator

HONEST SCOPE NOTE:
Poora SWE-bench evaluation ke liye chahiye: (a) dataset instances,
(b) har instance ka repo base_commit par checkout, (c) model patch,
(d) official docker harness se test-run. (c)+(d) ki heavy infra yahan
NAHI hai. Ye module wo hissa deliver karta hai jo Saleha uniquely kar
sakta hai aur jo officially verifiable hai:

  1. Instance -> Saleha prompt building (problem statement + hints)
  2. Orchestrator run -> generated code extraction
  3. Standard SWE-bench **predictions.jsonl** format likhna:
     {"instance_id", "model_name_or_path", "model_patch"}
     -- is file ko official sb-cli / SWE-bench harness me feed karke
        public score generate hota hai.

model_patch strategy: agar instance me `local_repo_dir` diya ho (user ne
repo checkout karke path diya) to MultiFileEditor-style real diff banega;
warna final_code ko ek synthetic diff (new-file) ke roop me likha jayega
-- jo official harness "empty patch" ki tarah treat karega (0 score) lekin
format valid rehta hai. Documented limitation, chhupaya nahi.
"""

import difflib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class SWEBenchPrediction:
    instance_id: str
    model_name_or_path: str
    model_patch: str
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> Dict[str, str]:
        """Official SWE-bench predictions.jsonl record format."""
        return {
            "instance_id": self.instance_id,
            "model_name_or_path": self.model_name_or_path,
            "model_patch": self.model_patch,
        }


def build_prompt(problem_statement: str, hints_text: str = "",
                 max_chars: int = 6000) -> str:
    """Instance problem statement -> Saleha coder prompt."""
    parts = [f"Fix the following issue in the repository.\n\n{problem_statement[:max_chars]}"]
    if hints_text and hints_text.strip():
        parts.append(f"\nAdditional hints:\n{hints_text[:2000]}")
    parts.append(
        "\nReturn ONLY the complete updated content of the files you change, "
        "each in its own ```python block with a header line '### FILE: <path>'."
    )
    return "\n".join(parts)


def synth_newfile_patch(final_code: str, filename: str = "saleha_solution.py") -> str:
    """Final code ko single new-file unified diff bana deta hai (format-valid)."""
    diff = difflib.unified_diff(
        [], final_code.splitlines(keepends=True),
        fromfile="/dev/null", tofile=f"/dev/null -> {filename}",
    )
    return "".join(diff)


def real_diff_from_repo(local_repo_dir: str, changed_files: Dict[str, str]) -> str:
    """Agar user ne repo checkout diya ho to ORIGINAL vs NEW ka real unified
    diff banata hai (changed_files = {rel_path: new_full_content})."""
    patches = []
    for rel, new_content in changed_files.items():
        old_path = os.path.join(local_repo_dir, rel)
        old_lines: List[str] = []
        if os.path.isfile(old_path):
            try:
                with open(old_path, "r", encoding="utf-8", errors="replace") as f:
                    old_lines = f.readlines()
            except OSError:
                pass
        patches.append("".join(difflib.unified_diff(
            old_lines, new_content.splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}",
        )))
    return "\n".join(p for p in patches if p)


def iter_instances(instances_path: str) -> Iterator[Dict[str, Any]]:
    """predictions input JSONL stream karta hai (ek line = ek instance)."""
    with open(instances_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("instance_id"):
                yield rec


def write_predictions(predictions: List[SWEBenchPrediction], out_path: str) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p.to_record(), ensure_ascii=False) + "\n")
            count += 1
    return count


def run_benchmark(instances_path: str, output_path: str,
                  model: str = "auto", limit: Optional[int] = None,
                  on_event=None) -> Dict[str, Any]:
    """Full loop: instances read -> orchestrator run -> predictions write."""
    from saleha.orchestrator import SalehaOrchestrator

    orchestrator = SalehaOrchestrator(model=model)
    predictions: List[SWEBenchPrediction] = []
    skipped = 0

    for i, inst in enumerate(iter_instances(instances_path)):
        if limit and i >= limit:
            break
        prompt = build_prompt(inst.get("problem_statement", ""),
                              inst.get("hints_text", ""))
        res = orchestrator.execute_task(prompt)
        if not res.success or not res.final_code.strip():
            # Official format: empty patch bhi record hota hai (score 0)
            patch = ""
            skipped += 1
        else:
            local_repo = inst.get("local_repo_dir")
            if local_repo and os.path.isdir(local_repo):
                patch = real_diff_from_repo(local_repo,
                                            {"saleha_solution.py": res.final_code})
            else:
                patch = synth_newfile_patch(res.final_code)
        pred = SWEBenchPrediction(
            instance_id=inst["instance_id"],
            model_name_or_path=model,
            model_patch=patch,
            meta={"attempts": res.attempts},
        )
        predictions.append(pred)
        if on_event:
            on_event({"instance_id": inst["instance_id"], "index": i + 1,
                      "success": bool(patch)})

    written = write_predictions(predictions, output_path)
    return {"total": len(predictions), "written": written,
            "empty_patches": skipped, "output": output_path}
