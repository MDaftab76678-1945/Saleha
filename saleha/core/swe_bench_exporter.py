"""
Saleha Core: SWE-bench Official Exporter & Scorecard Generator

Exports Saleha benchmark evaluation runs into the official SWE-bench
prediction format (`all_preds.jsonl`) required by the SWE-bench evaluation
harness, and generates publication-ready markdown scorecards.

Format specification:
{
  "instance_id": "<repo_owner>__<repo_name>-<issue_number>",
  "model_patch": "<unified_diff_patch>",
  "model_name_or_path": "saleha-v2.0"
}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from saleha.core.benchmark_reporter import BenchmarkRun
from saleha.core.swe_leaderboard import TaskResult


@dataclass
class SWEBenchPrediction:
    instance_id: str
    model_patch: str
    model_name_or_path: str = "saleha-v2.0"

    def to_dict(self) -> Dict[str, str]:
        return {
            "instance_id": self.instance_id,
            "model_patch": self.model_patch,
            "model_name_or_path": self.model_name_or_path,
        }


class SWEBenchExporter:
    """Exports benchmark runs into official SWE-bench format."""

    def __init__(self, model_name: str = "saleha-v2.0"):
        self.model_name = model_name

    def export_predictions(
        self,
        run: BenchmarkRun,
        output_file: str = "all_preds.jsonl",
        task_results: Optional[List[TaskResult]] = None,
    ) -> str:
        """Writes predictions to official jsonl format."""
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        preds = []
        if task_results:
            for tr in task_results:
                pred = SWEBenchPrediction(
                    instance_id=tr.task_id,
                    model_patch=tr.fix_applied or "",
                    model_name_or_path=self.model_name,
                )
                preds.append(pred)
        else:
            # Fallback using metadata in run
            results_meta = run.metadata.get("results", []) if run.metadata else []
            for item in results_meta:
                pred = SWEBenchPrediction(
                    instance_id=item.get("task_id", "unknown"),
                    model_patch=item.get("patch", ""),
                    model_name_or_path=self.model_name,
                )
                preds.append(pred)

        tmp_file = f"{output_file}.tmp.{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            for p in preds:
                f.write(json.dumps(p.to_dict()) + "\n")

        os.replace(tmp_file, output_file)
        return os.path.abspath(output_file)

    def generate_leaderboard_scorecard(
        self,
        run: BenchmarkRun,
        dataset_name: str = "SWE-bench Lite",
    ) -> str:
        """Generates a publication-ready markdown scorecard for PapersWithCode/HuggingFace."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        pass_rate = run.score_pct

        md = f"""# 🏆 SWE-bench Evaluation Scorecard: {self.model_name}

**Dataset**: `{dataset_name}` | **Evaluated At**: `{ts}` | **Execution**: 100% Local ($0 Cost)

## 📊 Summary Metrics

| Metric | Value |
|---|:---:|
| **Total Instances Evaluated** | {run.total_tasks} |
| **Instances Resolved (PASS)** | {run.solved} |
| **Pass@1 Rate** | **{pass_rate:.2f}%** |
| **Avg Duration Per Task** | {run.avg_time_sec:.2f}s |

---

## ⚔️ Leaderboard Comparison

| Agent / Model | Pass@1 Score | Cloud Cost / Instance | Open Source / Local |
|---|:---:|:---:|:---:|
| **🤖 {self.model_name} (Ollama)** | **{pass_rate:.2f}%** | **$0.00** | **✅ 100% Local** |
| Moatless Tools (Claude 3.5 Sonnet) | 38.00% | ~$4.20 | ❌ Cloud API |
| OpenHands (Claude 3.5 Sonnet) | 37.76% | ~$6.50 | ❌ Cloud API |
| Agentless (GPT-4o) | 27.33% | ~$2.10 | ❌ Cloud API |
| Devin (Cognition) | 13.86% | ~$15.00 | ❌ Proprietary ($500/mo) |
| SWE-agent (GPT-4o) | 12.47% | ~$3.80 | ❌ Cloud API |

---

## 📝 Instance Breakdown

| Instance ID | Solved | Status |
|---|:---:|:---:|
"""
        results_meta = run.metadata.get("results", []) if run.metadata else []
        for r in results_meta:
            solved = r.get("solved", False)
            status = "✅ PASS" if solved else "❌ FAIL"
            task_id = r.get("task_id", "task")
            md += f"| `{task_id}` | {status} | {'Resolved' if solved else 'Unresolved'} |\n"

        return md

