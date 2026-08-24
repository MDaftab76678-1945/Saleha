"""
Saleha Harness: Main Orchestration Engine

Dispatches multi-domain benchmark tasks to parallel execution workers, runs code in
sandboxes, verifies execution output against assertions, and aggregates Pass@k metrics.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

from saleha.harness.benchmarks import BenchmarkCatalog, BenchmarkTaskSpec
from saleha.harness.metrics import HarnessTaskResult, compute_benchmark_summary, estimate_pass_at_k
from saleha.harness.reporter import HarnessReport, reporter
from saleha.core.code_executor import CodeExecutor
from saleha.orchestrator import SalehaOrchestrator


class SalehaHarness:
    """Industrial-strength benchmark evaluation harness."""

    def __init__(self):
        self.executor = CodeExecutor()

    def _evaluate_single_task(self, task: BenchmarkTaskSpec, model: str, dry_run: bool = False) -> HarnessTaskResult:
        start_t = time.time()

        if dry_run:
            return HarnessTaskResult(
                task_id=task.id,
                benchmark=task.benchmark,
                prompt=task.prompt,
                passed=True,
                attempts_used=1,
                latency_sec=0.01,
                tokens_generated=50,
                tokens_per_sec=500.0
            )

        try:
            orchestrator = SalehaOrchestrator(model=model, max_healing_attempts=2)
            orch_res = orchestrator.execute_task(task.prompt)
            code = orch_res.final_code

            test_payload = f"{code}\n\n{task.test_code}"
            exec_res = self.executor.execute(test_payload)
            elapsed = round(time.time() - start_t, 2)

            passed = exec_res.success and "HARNESS_TEST_PASSED" in exec_res.output
            tokens = max(1, len(code) // 4)
            tok_sec = round(tokens / max(0.01, elapsed), 1)

            return HarnessTaskResult(
                task_id=task.id,
                benchmark=task.benchmark,
                prompt=task.prompt,
                passed=passed,
                attempts_used=orch_res.attempts,
                latency_sec=elapsed,
                tokens_generated=tokens,
                tokens_per_sec=tok_sec,
                error_detail=None if passed else exec_res.output
            )
        except Exception as e:
            elapsed = round(time.time() - start_t, 2)
            return HarnessTaskResult(
                task_id=task.id,
                benchmark=task.benchmark,
                prompt=task.prompt,
                passed=False,
                attempts_used=1,
                latency_sec=elapsed,
                error_detail=str(e)
            )

    def evaluate(
        self,
        model: str = "auto",
        benchmark: str = "all",
        limit: Optional[int] = None,
        workers: int = 4,
        dry_run: bool = False
    ) -> HarnessReport:
        """Executes multi-domain benchmarks in parallel and returns aggregated report."""
        tasks = BenchmarkCatalog.get_benchmarks(benchmark)
        if limit:
            tasks = tasks[:limit]

        results_by_suite: Dict[str, List[HarnessTaskResult]] = {}
        all_results: List[HarnessTaskResult] = []

        if dry_run or workers <= 1:
            for task in tasks:
                res = self._evaluate_single_task(task, model=model, dry_run=dry_run)
                results_by_suite.setdefault(res.benchmark, []).append(res)
                all_results.append(res)
        else:
            with ThreadPoolExecutor(max_workers=min(workers, len(tasks) or 1)) as pool:
                future_map = {
                    pool.submit(self._evaluate_single_task, t, model, dry_run): t
                    for t in tasks
                }
                for fut in as_completed(future_map):
                    res = fut.result()
                    results_by_suite.setdefault(res.benchmark, []).append(res)
                    all_results.append(res)

        # Compute summaries
        summaries = {}
        for suite_name, suite_results in results_by_suite.items():
            summaries[suite_name] = compute_benchmark_summary(suite_name, suite_results)

        total = len(all_results)
        passed = sum(1 for r in all_results if r.passed)
        pass_1 = round((passed / total) * 100, 2) if total else 0.0
        # Real unbiased Pass@k estimator (metrics.py) -- pehle fake
        # "pass_at_1 * 1.05" formula tha jo report ko misleading banata tha.
        pass_5 = round(estimate_pass_at_k(total, passed, k=min(5, total)) * 100, 2) if total else 0.0
        avg_lat = round(sum(r.latency_sec for r in all_results) / total, 2) if total else 0.0
        avg_tok_sec = round(sum(r.tokens_per_sec for r in all_results) / total, 1) if total else 0.0

        report = HarnessReport(
            model_name=model,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            total_tasks=total,
            overall_pass_at_1=pass_1,
            overall_pass_at_5=pass_5,
            avg_latency_sec=avg_lat,
            avg_tokens_per_sec=avg_tok_sec,
            benchmark_summaries=summaries
        )

        reporter.save_report(report)
        return report


# Global instance
harness = SalehaHarness()

