"""
Saleha Core: SWE-Bench-style Benchmark Harness (SWEBenchRunner)

Runs an end-to-end resolution attempt (plan -> generate -> test) against a
benchmark instance and checks whether the *actual generated code* satisfies
the instance's test assertion.

This is not the official SWE-bench harness -- see saleha/core/swe_bench_runner.py
(underscore between "swe" and "bench") for the module that produces standard
predictions.jsonl for the real SWE-bench evaluation pipeline, and is explicit
about that gap in its own docstring. This module is a smaller, in-process
scorecard: two illustrative default instances, not the SWE-bench dataset.

Previously this module's `_verify_assertion_in_sandbox` executed the test
assertion against a namespace pre-seeded with hand-written *correct*
implementations of `safe_divide` and `is_token_valid` -- so its "Pass@1"
score never actually depended on what the orchestrator generated. Any code
generation success (`exec_res.success`) was re-checked against those two
hardcoded correct answers, meaning the benchmark could not fail for either
of its own two default instances no matter what the model produced.

It now executes whatever code was actually generated (the orchestrator's
`final_code`, or nothing at all) and runs the assertion against *that*
namespace. If the generated code never defines the function the assertion
needs, the assertion fails with a NameError, which is reported honestly
as unresolved.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.orchestrator import SalehaOrchestrator
from saleha.core.smart_router import smart_router


@dataclass
class SWEBenchTask:
    """Represents a standardized SWE-Bench benchmark instance."""
    instance_id: str
    repo_name: str
    problem_statement: str
    test_assertion: str
    expected_fix_type: str = "bugfix"
    # For "mock" mode only: code to test as though it had been generated,
    # so the harness itself is exercisable offline. Real runs ignore this
    # and use whatever the orchestrator actually produced.
    mock_generated_code: str = ""


@dataclass
class SWEBenchTaskOutcome:
    """Outcome for an individual benchmark problem."""
    instance_id: str
    resolved: bool
    attempts: int
    duration_sec: float
    used_real_model: bool
    summary: str


@dataclass
class SWEBenchBenchmarkReport:
    """Consolidated benchmark evaluation report across all instances."""
    total_instances: int
    resolved_instances: int
    pass_at_1_percent: float
    average_duration_sec: float
    task_outcomes: List[SWEBenchTaskOutcome] = field(default_factory=list)
    summary: str = ""


class SWEBenchRunner:
    """SWE-Bench-style evaluation and scorecard harness."""

    def __init__(self, model: str = "auto"):
        """Initializes the SWE-bench runner with dynamic model resolution."""
        self.model = self._resolve_model(model)
        self.default_instances = [
            SWEBenchTask(
                instance_id="saleha__math-001",
                repo_name="core/math_engine",
                problem_statement="ZeroDivisionError when computing risk score with zero denominator",
                test_assertion="assert safe_divide(10, 0) == 0.0",
                mock_generated_code="def safe_divide(a, b):\n    return 0.0 if b == 0 else a / b\n",
            ),
            SWEBenchTask(
                instance_id="saleha__auth-002",
                repo_name="core/auth_service",
                problem_statement="Token expired exception when timestamp is precisely on expiry boundary",
                test_assertion="assert is_token_valid(current_time=1000, expiry_time=1000) is False",
                mock_generated_code="def is_token_valid(current_time, expiry_time):\n    return current_time < expiry_time\n",
            ),
        ]

    def _resolve_model(self, requested_model: str) -> str:
        """Resolves active model via SmartRouter or test environment."""
        if requested_model != "auto":
            return requested_model
        if os.environ.get("SALEHA_TEST_MODE") == "1":
            return "mock"
        try:
            best = smart_router.select_model_for_task("code", 0.7)
            return best if best else "mock"
        except Exception:
            return "mock"

    def _run_assertion_against_code(self, generated_code: str, assertion_str: str) -> bool:
        """Executes `generated_code` to build a namespace, then evaluates
        `assertion_str` against it. Returns False on any exception, including
        the generated code failing to define whatever the assertion needs --
        there is no fallback to a pre-written correct implementation."""
        namespace: Dict[str, Any] = {}
        try:
            if generated_code:
                exec(generated_code, namespace)
            exec(assertion_str, namespace)
            return True
        except Exception:
            return False

    def evaluate_task(self, task: SWEBenchTask) -> SWEBenchTaskOutcome:
        """Runs a resolution attempt on a single instance and checks the
        actually-generated code against the instance's test assertion."""
        t_start = time.time()
        goal = f"Fix SWE-Bench Issue in {task.repo_name}:\n{task.problem_statement}\nEnsure: {task.test_assertion}"

        if self.model == "mock":
            # No model is invoked here -- this path exists so the harness
            # itself (assertion execution, scoring, reporting) can be tested
            # offline. `mock_generated_code` stands in for what a real run
            # would have produced; leaving it empty is a valid way to check
            # that an assertion needing real code correctly fails.
            resolved = self._run_assertion_against_code(task.mock_generated_code, task.test_assertion)
            attempts = 1
            used_real_model = False
        else:
            orchestrator = SalehaOrchestrator(model=self.model, max_healing_attempts=2)
            exec_res = orchestrator.execute_task(goal)
            resolved = exec_res.success and self._run_assertion_against_code(
                exec_res.final_code, task.test_assertion
            )
            attempts = exec_res.attempts
            used_real_model = True

        dur = round(time.time() - t_start, 2)
        mode_note = "" if used_real_model else " [mock mode: no model invoked]"
        summary = f"Instance {task.instance_id}: {'RESOLVED' if resolved else 'UNRESOLVED'} in {dur}s ({attempts} attempts){mode_note}."

        return SWEBenchTaskOutcome(
            instance_id=task.instance_id,
            resolved=resolved,
            attempts=attempts,
            duration_sec=dur,
            used_real_model=used_real_model,
            summary=summary,
        )

    def run_benchmark_suite(self, tasks: Optional[List[SWEBenchTask]] = None) -> SWEBenchBenchmarkReport:
        """Executes full benchmark evaluation across test instances and calculates Pass@1."""
        target_tasks = tasks or self.default_instances
        outcomes: List[SWEBenchTaskOutcome] = []

        for t in target_tasks:
            out = self.evaluate_task(t)
            outcomes.append(out)

        total = len(outcomes)
        resolved = sum(1 for o in outcomes if o.resolved)
        pass_rate = round((resolved / total) * 100.0, 1) if total > 0 else 0.0
        avg_dur = round(sum(o.duration_sec for o in outcomes) / total, 2) if total > 0 else 0.0
        any_mock = any(not o.used_real_model for o in outcomes)

        summary = f"SWE-Bench Benchmark: {resolved}/{total} tasks resolved ({pass_rate}% Pass@1, avg {avg_dur}s per task)."
        if any_mock:
            summary += " [Includes mock-mode instances where no model was invoked; not a real capability measurement.]"

        return SWEBenchBenchmarkReport(
            total_instances=total,
            resolved_instances=resolved,
            pass_at_1_percent=pass_rate,
            average_duration_sec=avg_dur,
            task_outcomes=outcomes,
            summary=summary,
        )


swebench_runner = SWEBenchRunner()


if __name__ == "__main__":
    _sbr = SWEBenchRunner(model="mock")
    _rep = _sbr.run_benchmark_suite()
