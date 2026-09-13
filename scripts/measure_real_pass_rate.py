"""Measure what Saleha actually solves. No literals, no leaderboard, no ranks.

## Why this exists

`NOTEBOOK_IMPORT.md` records passes of removing fabricated benchmark numbers
from this repository: "97.2% SWE-bench, Rank #1, CERTIFIED", "All 12 unit
tests passed in 0.42s", "GLOBAL_FRONTIER_LEADER". Every one was a literal
someone typed. This script is the opposite of all of that. Each task has a
real prompt, a real test that fails on wrong code -- verified before the run
-- and execution in a subprocess with a timeout.

## Where the engine lives now

The tasks and the runner used to be defined in this file. They now live in
`saleha/core/real_task_bench.py`, because `pyproject.toml` ships only
`saleha*` and `scripts/` is not a package -- so this measurement was
unreachable from the installed package and from every CLI command, while the
fabricated harnesses were the ones wired up. Keeping a second copy here would
let the two drift, so this script is now a thin front end over the shipped
engine, and `saleha benchmark-local` is the same thing as a command.

## What the number does and does not mean

Twelve small, self-contained programming problems on one machine and one
local model. It is not SWE-bench, it is not a leaderboard position, and
twelve tasks is a small sample -- report a run as "10/12 with these two
failures", never as a percentage standing on its own.

Usage:
    python scripts/measure_real_pass_rate.py
    python scripts/measure_real_pass_rate.py --model qwen3:8b
    python scripts/measure_real_pass_rate.py --verify-tests-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from saleha.core.real_task_bench import (  # noqa: E402
    DEFAULT_MODEL,
    TASKS,
    run_benchmark,
    scored_swebench_availability,
    verify_tests_can_fail,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure real local pass rate.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--verify-tests-only", action="store_true",
                        help="only check that each test fails on wrong code")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args()

    print(f"Verifying {len(TASKS)} tests can actually fail...")
    broken = verify_tests_can_fail()
    if broken:
        print(f"  REFUSING TO RUN: these tests pass against deliberately "
              f"wrong code: {broken}")
        print("  A test that cannot fail cannot measure anything.")
        return 2
    print(f"  all {len(TASKS)} tests fail on wrong code, as they must.\n")

    if args.verify_tests_only:
        return 0

    total = len(TASKS if args.limit is None else TASKS[:args.limit])
    counter = {"n": 0}

    def show(outcome):
        counter["n"] += 1
        print(f"[{counter['n']:2d}/{total}] {outcome.task_id:24s} "
              f"{'PASS' if outcome.passed else 'FAIL'}  "
              f"({outcome.duration_sec}s)"
              + (f"  {outcome.error}" if outcome.error else ""))

    report = run_benchmark(model=args.model, limit=args.limit, on_task=show)

    if not report.did_run:
        print(f"\nDid not run: {report.refused_reason}")
        return 2

    print()
    print("=" * 62)
    print(f"  {report.passed}/{report.total} tasks passed"
          f"   model {report.model}   {report.total_sec}s")
    print("=" * 62)

    failures = [o for o in report.outcomes if not o.passed]
    if failures:
        print("\nFailures:")
        for o in failures:
            print(f"  {o.task_id:24s} {o.error}")

    print("\nThis is twelve small self-contained problems on one local model."
          "\nIt is not SWE-bench and not a leaderboard position. Report it as "
          f"\n\"{report.passed}/{report.total} with these failures\", never as "
          "a percentage on its own.")

    available, detail = scored_swebench_availability()
    print(f"\nScored SWE-bench {'is available' if available else 'cannot run'} "
          f"here: {detail}")

    if args.as_json:
        print(json.dumps({
            "model": report.model,
            "passed": report.passed,
            "total": report.total,
            "duration_sec": report.total_sec,
            "results": [{"task": o.task_id, "passed": o.passed,
                         "duration_sec": o.duration_sec, "error": o.error}
                        for o in report.outcomes],
        }, indent=2))

    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    sys.exit(main())
