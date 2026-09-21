"""
Saleha Core: a small self-check that the sandbox executor runs known-good code.

HONEST SCOPE NOTE -- read before using any number this module prints.

This is NOT SWE-bench. It shares none of SWE-bench's properties:

  * The three instances below are **not bugs**. Each `base_code` already
    satisfies its own `test_patch` before any agent touches it -- verified
    directly: all three pass when executed as-is.
  * No model is invoked anywhere in this file. No patch is synthesized, no
    repository is checked out, no bug is localized.

So the only thing a run establishes is that `CodeExecutor` can execute
correct Python and observe its output. That is worth checking, and it is all
this checks. The class is named `SandboxSelfCheck` to say so.

It used to be called `SWEBenchHarness`, report a `pass_rate` as "Pass@1", and
render a "Saleha AI Benchmark Leaderboard" -- for a suite that could only
ever return 100%, because the code was pre-fixed and no agent was involved.
`--dry-run` was worse still: it skipped execution entirely and hardcoded
`resolved = True`, so `saleha bench --dry-run` printed "Pass Rate: 100.0%"
under the heading "Official Benchmark Summary" having run nothing at all.

For a real measurement of what this project's models actually solve, see
`scripts/measure_real_pass_rate.py` -- every task there carries a
deliberately wrong implementation, and the script refuses to run unless the
tests fail against it first. For real SWE-bench predictions, see
`saleha/core/swe_bench_runner.py`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from saleha.core.code_executor import CodeExecutor


@dataclass
class SWEBenchTask:
    instance_id: str
    repo: str
    problem_statement: str
    base_code: str
    test_patch: str
    difficulty: str = "medium"


@dataclass
class SelfCheckResult:
    total_instances: int
    # Instances whose known-good code executed and printed its marker.
    executed_ok: int
    avg_latency_sec: float
    # False whenever no instance was actually executed (e.g. list_only).
    did_execute: bool = True
    results: List[Dict[str, Any]] = field(default_factory=list)

    def render_markdown(self) -> str:
        if not self.did_execute:
            return ("# Sandbox self-check -- NOT RUN\n"
                    "Nothing was executed, so there is no result to report.")
        lines = [
            "# Sandbox self-check",
            "",
            "Executes pre-written correct code and checks the sandbox observes "
            "its output. No model is invoked and no bug is fixed, so this is "
            "not a capability measurement -- see "
            "`scripts/measure_real_pass_rate.py` for that.",
            "",
            f"- Instances executed cleanly: {self.executed_ok}/{self.total_instances}",
            f"- Average latency: {self.avg_latency_sec}s",
            "",
            "| Instance | Source | Executed cleanly | Latency |",
            "|---|---|---|---|",
        ]
        for r in self.results:
            status = "yes" if r["executed_ok"] else "NO"
            lines.append(
                f"| `{r['instance_id']}` | `{r['repo']}` | {status} | {r['latency_sec']}s |"
            )
        return "\n".join(lines)


SWE_BENCH_TASKS: List[SWEBenchTask] = [
    SWEBenchTask(
        instance_id="SWE-001-URLPARSER",
        repo="saleha/web-router",
        problem_statement="Bug: URL query parameters with multiple values are overwritten instead of preserved as lists.",
        base_code=(
            "def parse_query(qs: str) -> dict:\n"
            "    res = {}\n"
            "    for pair in qs.split('&'):\n"
            "        if '=' in pair:\n"
            "            k, v = pair.split('=', 1)\n"
            "            if k in res:\n"
            "                if not isinstance(res[k], list):\n"
            "                    res[k] = [res[k]]\n"
            "                res[k].append(v)\n"
            "            else:\n"
            "                res[k] = v\n"
            "    return res\n"
        ),
        test_patch=(
            "d = parse_query('tag=ai&tag=python&author=saleha')\n"
            "assert d['tag'] == ['ai', 'python']\n"
            "assert d['author'] == 'saleha'\n"
            "print('SWE_BENCH_VERIFIED')"
        ),
        difficulty="easy"
    ),
    SWEBenchTask(
        instance_id="SWE-002-RATELIMIT-EXPIRY",
        repo="saleha/middleware",
        problem_statement="Bug: Expired tokens in rate limiter cache cause memory leak because clean_expired() raises KeyError.",
        base_code=(
            "import time\n\n"
            "class Cache:\n"
            "    def __init__(self):\n"
            "        self.store = {}\n"
            "    def set(self, k, v, ttl=1):\n"
            "        self.store[k] = (v, time.time() + ttl)\n"
            "    def clean_expired(self):\n"
            "        now = time.time()\n"
            "        expired = [k for k, (_, exp) in self.store.items() if exp <= now]\n"
            "        for k in expired:\n"
            "            self.store.pop(k, None)\n"
            "        return len(expired)\n"
        ),
        test_patch=(
            "c = Cache()\n"
            "c.set('key1', 'val1', ttl=0.01)\n"
            "time.sleep(0.05)\n"
            "cleaned = c.clean_expired()\n"
            "assert cleaned == 1\n"
            "assert 'key1' not in c.store\n"
            "print('SWE_BENCH_VERIFIED')"
        ),
        difficulty="medium"
    ),
    SWEBenchTask(
        instance_id="HUMANEVAL-001-CLOSE-ELEMENTS",
        repo="saleha/math-utils",
        problem_statement="Check if in given list of numbers, are any two numbers closer to each other than given threshold.",
        base_code=(
            "def has_close_elements(numbers: list, threshold: float) -> bool:\n"
            "    for idx, elem in enumerate(numbers):\n"
            "        for idx2, elem2 in enumerate(numbers):\n"
            "            if idx != idx2:\n"
            "                distance = abs(elem - elem2)\n"
            "                if distance < threshold:\n"
            "                    return True\n"
            "    return False\n"
        ),
        test_patch=(
            "assert has_close_elements([1.0, 2.0, 3.0], 0.5) is False\n"
            "assert has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) is True\n"
            "print('SWE_BENCH_VERIFIED')"
        ),
        difficulty="easy"
    )
]


class SandboxSelfCheck:
    """Executes known-good code and checks the sandbox observes its output."""

    def __init__(self, tasks: Optional[List[SWEBenchTask]] = None) -> None:
        self.tasks = tasks or SWE_BENCH_TASKS
        self.executor = CodeExecutor()

    def run_self_check(self, limit: Optional[int] = None,
                       list_only: bool = False) -> SelfCheckResult:
        """Runs each instance's code and records whether it executed cleanly.

        `list_only` replaces the old `dry_run`, which hardcoded
        `resolved = True` for every instance and reported a 100% pass rate
        having executed nothing. Listing what would run is a legitimate thing
        to want; claiming it passed is not, so `list_only` returns
        `did_execute=False` and an `executed_ok` of 0 rather than a number
        that reads like a result.
        """
        tasks_to_run = self.tasks[:limit] if limit else self.tasks

        if list_only:
            return SelfCheckResult(
                total_instances=len(tasks_to_run),
                executed_ok=0,
                avg_latency_sec=0.0,
                did_execute=False,
                results=[{
                    "instance_id": t.instance_id,
                    "repo": t.repo,
                    "executed_ok": None,
                    "latency_sec": 0.0,
                    "difficulty": t.difficulty,
                } for t in tasks_to_run],
            )

        ok_count = 0
        total_time = 0.0
        results = []

        for task in tasks_to_run:
            start_t = time.time()
            combined_code = f"{task.base_code}\n\n{task.test_patch}"
            exec_res = self.executor.execute(combined_code)
            executed_ok = exec_res.success and "SWE_BENCH_VERIFIED" in exec_res.output
            elapsed = round(time.time() - start_t, 2)

            if executed_ok:
                ok_count += 1
            total_time += elapsed

            results.append({
                "instance_id": task.instance_id,
                "repo": task.repo,
                "executed_ok": executed_ok,
                "latency_sec": elapsed,
                "difficulty": task.difficulty,
            })

        avg_latency = round(total_time / len(tasks_to_run), 2) if tasks_to_run else 0.0

        return SelfCheckResult(
            total_instances=len(tasks_to_run),
            executed_ok=ok_count,
            avg_latency_sec=avg_latency,
            did_execute=True,
            results=results,
        )


# Global instance
sandbox_self_check = SandboxSelfCheck()


