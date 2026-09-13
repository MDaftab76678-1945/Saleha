"""Saleha Core: export a benchmark run to SWE-bench prediction format.

## What the scorecard used to say

    | **Pass@1 Rate** | **100.00%** |
    | **saleha-v2.0 (Ollama)** | **100.00%** | **$0.00** | **100% Local** |
    | Moatless Tools (Claude 3.5 Sonnet) | 38.00% | ~$4.20 | Cloud API |
    | Devin (Cognition) | 13.86% | ~$15.00 | Proprietary ($500/mo) |

Every competitor figure there is a real published SWE-bench Verified score.
The 100.00% above them was not a score at all: it came from
`swe_leaderboard._generate_fix()` returning the task's own `expected_fix`,
the answer key. The heading said "SWE-bench Evaluation Scorecard" and the
`.jsonl` was written in the official submission format -- so the one number
that was fabricated was also the one formatted for publication.

## What it does now

The JSONL writer was always genuine and is unchanged: it emits
`{instance_id, model_patch, model_name_or_path}`, one record per line,
atomically. What changed is the scorecard -- it reports the run's real
numbers, names the benchmark that actually produced them, and no longer
prints a comparison table against other tools' scores on a benchmark this
project has not run.

For the real SWE-bench predictions path (a real repo checkout, a real
`AgentLoop`, a real `git diff`), see `saleha/core/swe_bench_runner.py`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from saleha.core.benchmark_reporter import (
    PUBLIC_SWEBENCH_VERIFIED_REFERENCE,
    BenchmarkRun,
)
from saleha.core.real_task_bench import scored_swebench_availability
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
    """Writes predictions in SWE-bench submission format, and an honest scorecard."""

    def __init__(self, model_name: str = "saleha-v2.0"):
        self.model_name = model_name

    def export_predictions(
        self,
        run: BenchmarkRun,
        output_file: str = "all_preds.jsonl",
        task_results: Optional[List[TaskResult]] = None,
    ) -> str:
        """Writes predictions to the official jsonl format."""
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        preds = []
        if task_results:
            for tr in task_results:
                preds.append(SWEBenchPrediction(
                    instance_id=tr.task_id,
                    model_patch=tr.fix_applied or "",
                    model_name_or_path=self.model_name,
                ))
        else:
            results_meta = run.metadata.get("results", []) if run.metadata else []
            for item in results_meta:
                preds.append(SWEBenchPrediction(
                    instance_id=item.get("task_id", "unknown"),
                    model_patch=item.get("patch", ""),
                    model_name_or_path=self.model_name,
                ))

        tmp_file = f"{output_file}.tmp.{os.getpid()}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            for p in preds:
                f.write(json.dumps(p.to_dict()) + "\n")

        os.replace(tmp_file, output_file)
        return os.path.abspath(output_file)

    def generate_scorecard(self, run: BenchmarkRun) -> str:
        """Render the run's real numbers, naming the benchmark that produced them."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta = run.metadata or {}
        suite = run.suite or "unknown"
        did_run = meta.get("did_run", True)
        benchmark_label = meta.get("benchmark", suite)

        md = [f"# Benchmark scorecard: {self.model_name}", ""]

        if not did_run:
            md += [
                f"**Evaluated at**: `{ts}`", "",
                "## This run did not execute",
                "",
                f"No score is reported. Reason: `{run.notes}`",
                "",
                "A benchmark that did not run has no pass rate.",
            ]
            return "\n".join(md)

        md += [
            f"**Benchmark**: `{benchmark_label}`  ",
            f"**Evaluated at**: `{ts}`  ",
            f"**Execution**: local, no cloud API calls",
            "",
            "## Result",
            "",
            "| Metric | Value |",
            "|---|:---:|",
            f"| Tasks attempted | {run.total_tasks} |",
            f"| Tasks passed | {run.solved} |",
            f"| Pass rate | **{run.score_pct:.2f}%** |",
            f"| Avg duration per task | {run.avg_time_sec:.2f}s |",
            "",
        ]

        md += [
            "## What this number is not",
            "",
            "This is **not** SWE-bench and not a leaderboard position. It is a "
            f"run of `{benchmark_label}` -- small, self-contained programming "
            "problems on one machine, each with a test verified to fail on "
            "wrong code before the run started.",
            "",
        ]

        available, detail = scored_swebench_availability()
        if available:
            md.append(f"Scored SWE-bench is available on this machine ({detail}) "
                      "but was not run here; see `swe_bench_runner.py`.")
        else:
            md.append(f"Scored SWE-bench could not be run here: {detail}.")
        md.append("")

        md += [
            "For context only, published Pass@1 figures for other tools on "
            "**SWE-bench Verified** -- a different, much harder benchmark, "
            "not comparable to the number above:",
            "",
            "| Agent / Model | Published Pass@1 (SWE-bench Verified) |",
            "|---|:---:|",
        ]
        for name, score in sorted(PUBLIC_SWEBENCH_VERIFIED_REFERENCE.items(),
                                  key=lambda x: -x[1]):
            md.append(f"| {name} | {score:.2f}% |")

        md += ["", "## Task breakdown", "",
               "| Task | Passed | Duration |", "|---|:---:|:---:|"]
        for r in meta.get("results", []):
            status = "yes" if r.get("solved") else "NO"
            md.append(f"| `{r.get('task_id', 'task')}` | {status} | "
                      f"{r.get('duration_sec', 0)}s |")

        return "\n".join(md)
