"""
Saleha Core: Local Model Benchmark Evaluator

Automated evaluation harness for benchmarking local Ollama coding models
(HumanEval-style coding challenges) measuring Pass@1 accuracy, latency, and self-healing rate.
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from saleha.core.code_executor import CodeExecutor


@dataclass
class BenchmarkTask:
    task_id: str
    prompt: str
    test_suite: str
    difficulty: str = "easy"


BENCHMARK_TASKS: List[BenchmarkTask] = [
    BenchmarkTask(
        task_id="EVAL001",
        prompt="Write a Python function `fibonacci(n: int) -> int` that returns the n-th Fibonacci number (0-indexed).",
        test_suite="assert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(7) == 13\nprint('TEST_PASSED')",
        difficulty="easy"
    ),
    BenchmarkTask(
        task_id="EVAL002",
        prompt="Write a Python function `is_palindrome(s: str) -> bool` that checks if a string is a palindrome ignoring case and non-alphanumeric characters.",
        test_suite="assert is_palindrome('A man, a plan, a canal: Panama') == True\nassert is_palindrome('race a car') == False\nprint('TEST_PASSED')",
        difficulty="easy"
    ),
    BenchmarkTask(
        task_id="EVAL003",
        prompt="Write a Python function `two_sum(nums: list, target: int) -> list` that returns indices of the two numbers such that they add up to target.",
        test_suite="assert two_sum([2,7,11,15], 9) in ([0,1], [1,0])\nassert two_sum([3,2,4], 6) in ([1,2], [2,1])\nprint('TEST_PASSED')",
        difficulty="medium"
    ),
    BenchmarkTask(
        task_id="EVAL004",
        prompt="Write a Python function `merge_intervals(intervals: list) -> list` that merges all overlapping intervals.",
        test_suite="assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]\nprint('TEST_PASSED')",
        difficulty="medium"
    ),
    BenchmarkTask(
        task_id="EVAL005",
        prompt="Write a Python function `deep_flatten(lst: list) -> list` that recursively flattens a nested list of arbitrary depth.",
        test_suite="assert deep_flatten([1, [2, [3, [4, 5]]]]) == [1, 2, 3, 4, 5]\nprint('TEST_PASSED')",
        difficulty="medium"
    )
]


@dataclass
class BenchmarkScore:
    model: str
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    avg_latency_sec: float
    task_results: List[Dict[str, Any]] = field(default_factory=list)


class ModelBenchmarkEvaluator:
    """Runs coding benchmarks on LLM models to assess generation quality and Pass@1."""

    def __init__(self, tasks: Optional[List[BenchmarkTask]] = None):
        self.tasks = tasks or BENCHMARK_TASKS
        self.executor = CodeExecutor()

    def run_benchmark(self, model: str = "auto", limit: Optional[int] = None, dry_run: bool = False) -> BenchmarkScore:
        from saleha.orchestrator import SalehaOrchestrator

        tasks_to_run = self.tasks[:limit] if limit else self.tasks
        passed_count = 0
        total_time = 0.0
        results = []

        orchestrator = SalehaOrchestrator(model=model, max_healing_attempts=2)

        for task in tasks_to_run:
            start_t = time.time()
            if dry_run:
                passed = True
                elapsed = 0.01
                code = "def placeholder(): pass"
            else:
                orch_res = orchestrator.execute_task(task.prompt)
                code = orch_res.final_code
                test_code = f"{code}\n\n{task.test_suite}"
                exec_res = self.executor.execute(test_code)
                passed = exec_res.success and "TEST_PASSED" in exec_res.output
                elapsed = round(time.time() - start_t, 2)

            if passed:
                passed_count += 1
            total_time += elapsed

            results.append({
                "task_id": task.task_id,
                "passed": passed,
                "latency_sec": elapsed,
                "difficulty": task.difficulty
            })

        pass_rate = round((passed_count / len(tasks_to_run)) * 100, 1) if tasks_to_run else 0.0
        avg_latency = round(total_time / len(tasks_to_run), 2) if tasks_to_run else 0.0

        return BenchmarkScore(
            model=model,
            total_tasks=len(tasks_to_run),
            passed_tasks=passed_count,
            pass_rate=pass_rate,
            avg_latency_sec=avg_latency,
            task_results=results
        )


# Global instance
evaluator = ModelBenchmarkEvaluator()

