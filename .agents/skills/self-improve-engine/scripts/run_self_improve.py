#!/usr/bin/env python3
"""CLI runner for the Saleha Autonomous Self-Improvement Engine.

Provides structured subcommands (status, cycle, batch, logs) following
agent skill guidelines with JSON file outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

# Ensure repository root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# repo root is 4 levels up: .agents/skills/self-improve-engine/scripts/ -> repo root
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from saleha.core.self_improve import (
    find_untested_module,
    run_self_improvement_cycle,
    read_log,
    SelfImproveResult,
    BRANCH_NAME,
    LOG_PATH,
    CORE_DIR,
    TEST_DIR,
    _run,
    _tested_on_auto_branch,
)


def _write_output(data: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Success! Data written to: {output_path}")


def cmd_status(args: argparse.Namespace) -> None:
    """Summarizes current coverage, pending modules, and auto-branch state."""
    tested_main = {
        f[len("test_"):-len(".py")]
        for f in os.listdir(TEST_DIR)
        if f.startswith("test_") and f.endswith(".py")
    }
    tested_auto = _tested_on_auto_branch()
    all_core_modules = sorted(
        f[:-3] for f in os.listdir(CORE_DIR)
        if f.endswith(".py") and not f.startswith("__")
    )
    untested = [m for m in all_core_modules if m not in tested_main and m not in tested_auto]

    # Inspect commits on auto/self-improve branch
    branch_proc = _run(["git", "log", BRANCH_NAME, "--oneline", "-n", "10"], cwd=REPO_ROOT)
    commits_on_auto = branch_proc.stdout.splitlines() if branch_proc.returncode == 0 else []

    recent_logs = read_log(limit=args.log_limit)

    report = {
        "repo_root": REPO_ROOT,
        "auto_branch": BRANCH_NAME,
        "total_core_modules": len(all_core_modules),
        "tested_on_main": len(tested_main),
        "tested_on_auto_branch": len(tested_auto),
        "untested_remaining": len(untested),
        "next_candidate": untested[0] if untested else None,
        "untested_modules": untested,
        "recent_auto_commits": commits_on_auto,
        "recent_log_entries": recent_logs[-5:],
    }
    _write_output(report, args.output)


def cmd_cycle(args: argparse.Namespace) -> None:
    """Runs a single autonomous self-improvement cycle."""
    result = run_self_improvement_cycle()
    report = {
        "timestamp": result.timestamp,
        "module": result.module,
        "goal": result.goal,
        "status": result.status,
        "detail": result.detail,
        "branch": result.branch,
        "commit_sha": result.commit_sha,
    }
    _write_output(report, args.output)
    if result.status == "committed":
        print(f"Cycle committed successfully: {result.module} (SHA: {result.commit_sha})")
    else:
        print(f"Cycle completed with status: {result.status} (detail: {result.detail[:100]}...)")


def cmd_batch(args: argparse.Namespace) -> None:
    """Runs N cycles sequentially, skipping modules that repeatedly fail
    generation OR repeatedly fail their pytest check (max 2 attempts each) --
    a module stuck on either failure mode used to consume the whole batch."""
    attempts = args.cycles
    skip_set = set()
    fail_counts: dict[str, int] = {}
    results = []
    committed_count = 0
    MAX_TRIES_PER_MODULE = 2

    print(f"Starting batch of up to {attempts} cycles...")
    for i in range(1, attempts + 1):
        res = run_self_improvement_cycle(skip=skip_set)
        results.append({
            "cycle_index": i,
            "timestamp": res.timestamp,
            "module": res.module,
            "status": res.status,
            "detail": res.detail[:200],
            "commit_sha": res.commit_sha,
        })
        if res.status == "committed":
            committed_count += 1
            print(f"[{i}/{attempts}] Committed: {res.module} (SHA: {res.commit_sha})")
        elif res.status == "no_candidate":
            print(f"[{i}/{attempts}] No remaining untested candidate modules.")
            break
        elif res.status in ("generation_failed", "test_failed"):
            print(f"[{i}/{attempts}] {res.status} for {res.module}")
            if res.module:
                key = res.module[:-3] if res.module.endswith(".py") else res.module
                fail_counts[key] = fail_counts.get(key, 0) + 1
                if fail_counts[key] >= MAX_TRIES_PER_MODULE:
                    skip_set.add(key)
                    print(f"  -> skipping {res.module} after {MAX_TRIES_PER_MODULE} failures")
        else:
            print(f"[{i}/{attempts}] Status: {res.status} for {res.module}")

    batch_report = {
        "requested_cycles": attempts,
        "completed_cycles": len(results),
        "committed_count": committed_count,
        "results": results,
    }
    _write_output(batch_report, args.output)


def cmd_logs(args: argparse.Namespace) -> None:
    """Inspects ~/.saleha/self_improve_log.jsonl with filtering."""
    logs = read_log(limit=args.limit)
    if args.status:
        logs = [l for l in logs if l.get("status") == args.status]
    report = {
        "log_path": LOG_PATH,
        "filter_status": args.status,
        "count": len(logs),
        "entries": logs,
    }
    _write_output(report, args.output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Saleha Autonomous Self-Improvement Engine CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Get engine status and candidate modules")
    p_status.add_argument("--output", required=True, help="Path to write JSON status report")
    p_status.add_argument("--log-limit", type=int, default=10, help="Number of recent logs to include")
    p_status.set_defaults(func=cmd_status)

    # cycle
    p_cycle = subparsers.add_parser("cycle", help="Execute one autonomous self-improvement cycle")
    p_cycle.add_argument("--output", required=True, help="Path to write JSON cycle result")
    p_cycle.set_defaults(func=cmd_cycle)

    # batch
    p_batch = subparsers.add_parser("batch", help="Run batch of cycles sequentially")
    p_batch.add_argument("--cycles", type=int, default=3, help="Number of cycles to attempt")
    p_batch.add_argument("--output", required=True, help="Path to write JSON batch report")
    p_batch.set_defaults(func=cmd_batch)

    # logs
    p_logs = subparsers.add_parser("logs", help="Inspect execution audit log")
    p_logs.add_argument("--limit", type=int, default=20, help="Number of log entries to fetch")
    p_logs.add_argument("--status", choices=["committed", "test_failed", "generation_failed", "no_candidate"],
                        help="Filter by outcome status")
    p_logs.add_argument("--output", required=True, help="Path to write JSON log entries")
    p_logs.set_defaults(func=cmd_logs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
