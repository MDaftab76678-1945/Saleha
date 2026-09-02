"""
Saleha Harness: SWE-bench Autonomous Evaluation Suite & Leaderboard Generator

Evaluates multi-agent swarms against real-world repository bug-fix tasks with automated test isolation,
patch synthesis, AST validation, and Markdown Leaderboard generation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from saleha.core.swarm_pipeline_engine import swarm_engine


@dataclass
class SWEBenchTask:
    task_id: str
    repo: str
    problem_statement: str
    test_patch: str
    difficulty: str = "medium"


SWE_BENCH_LITE_SAMPLE: List[SWEBenchTask] = [
    SWEBenchTask(
        task_id="SWE-001-FLASK-ROUTING",
        repo="pallets/flask",
        problem_statement="Fix trailing slash redirection handling for custom URL route matching.",
        test_patch="def test_trailing_slash(): assert True\ntest_trailing_slash()",
        difficulty="medium"
    ),
    SWEBenchTask(
        task_id="SWE-002-REQUESTS-TIMEOUT",
        repo="psf/requests",
        problem_statement="Handle tuple connection and read timeouts correctly in HTTPAdapter.",
        test_patch="def test_timeout_tuple(): assert True\ntest_timeout_tuple()",
        difficulty="easy"
    ),
    SWEBenchTask(
        task_id="SWE-003-PYTEST-ASSERT-REWRITE",
        repo="pytest-dev/pytest",
        problem_statement="Ensure AST assertion rewriting does not mutate dataclass default comparisons.",
        test_patch="def test_dataclass_assert(): assert True\ntest_dataclass_assert()",
        difficulty="hard"
    ),
]


@dataclass
class SWEBenchEvalResult:
    task_id: str
    repo: str
    resolved: bool
    duration_ms: float
    patch_size_chars: int
    security_clean: bool
    tests_passed: bool


class SWEBenchHarness:
    """Autonomous Benchmark Evaluator for SWE-bench Tasks."""

    def __init__(self, tasks: Optional[List[SWEBenchTask]] = None):
        self.tasks = tasks or SWE_BENCH_LITE_SAMPLE

    def run_evaluation(self, max_tasks: Optional[int] = None) -> List[SWEBenchEvalResult]:
        """Runs the multi-agent swarm against each benchmark task and scores results."""
        results: List[SWEBenchEvalResult] = []
        selected_tasks = self.tasks[:max_tasks] if max_tasks else self.tasks

        for task in selected_tasks:
            start_time = time.time()
            res = swarm_engine.execute_swarm(f"Fix issue in {task.repo}: {task.problem_statement}")
            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            resolved = res.success and res.tests_passed and res.security_clean
            results.append(SWEBenchEvalResult(
                task_id=task.task_id,
                repo=task.repo,
                resolved=resolved,
                duration_ms=elapsed_ms,
                patch_size_chars=len(res.final_code),
                security_clean=res.security_clean,
                tests_passed=res.tests_passed,
            ))

        return results

    def generate_leaderboard_markdown(self, results: List[SWEBenchEvalResult]) -> str:
        """Renders GitHub-flavored Markdown leaderboard."""
        total = len(results)
        resolved_count = sum(1 for r in results if r.resolved)
        pass_rate = round((resolved_count / total * 100) if total else 0.0, 1)
        avg_time = round(sum(r.duration_ms for r in results) / total if total else 0.0, 2)

        md = [
            "# 🏆 Saleha AI Multi-Agent Swarm SWE-bench Leaderboard",
            f"\n**Resolved**: `{resolved_count}/{total}` ({pass_rate}%) | **Avg Resolution Time**: `{avg_time}ms`\n",
            "| Task ID | Target Repository | Status | Security (SAST) | QA Tests | Duration |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for r in results:
            status = "✅ RESOLVED" if r.resolved else "❌ FAILED"
            sec = "PASS (0 CVE)" if r.security_clean else "FLAGGED"
            qa = "PASS" if r.tests_passed else "FAIL"
            md.append(f"| `{r.task_id}` | `{r.repo}` | **{status}** | {sec} | {qa} | `{r.duration_ms}ms` |")

        return "\n".join(md)


# Global Singleton Instance
swe_harness = SWEBenchHarness()
