#!/usr/bin/env python3
"""Darwinian Self-Evolution & Algorithmic Optimization Engine.

Benchmarks a target script against a genuinely mutated variant of itself
(reusing the real AST operator-flip mutator from the mutation-engine skill)
and reports a speedup only when the mutant is a different, test-passing
program. This does not synthesize new algorithms -- it can only try the
small set of operator-flip mutations the mutation engine already knows how
to generate, and most of those will fail the test gate and be reported as
such. It exists to catch the rare case where a mutation is both correct and
faster, not to claim general-purpose optimization.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[4]

MUTATION_ENGINE_SCRIPT = (
    REPO_ROOT / ".agents" / "skills" / "mutation-engine" / "scripts" / "run_mutation_test.py"
)


def _load_mutation_engine() -> Any:
    """Loads count_potential_mutations/generate_mutant from the real mutation-engine script."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_mutation_test", str(MUTATION_ENGINE_SCRIPT))
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load mutation engine at {MUTATION_ENGINE_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_test_command(test_command: str) -> bool:
    """Runs the validation command and returns True only on a clean exit."""
    proc = subprocess.run(
        test_command,
        shell=True,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode == 0


def measure_execution_speed(command: str, iterations: int = 3) -> float:
    """Measures average execution wall-clock time over multiple runs."""
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        t1 = time.perf_counter()
        if proc.returncode == 0:
            times.append(t1 - t0)
    return sum(times) / len(times) if times else 999.0


def run_evolution_cycle(target_script: Path, test_command: str, max_mutants: int = 5) -> Dict[str, Any]:
    """Tries genuine operator-flip mutants of target_script; ratifies only a
    mutant that is both test-passing and measurably faster than the original.
    """
    if not target_script.exists():
        return {"status": "ERROR", "message": f"Target not found: {target_script}"}

    engine = _load_mutation_engine()
    original_code = target_script.read_text(encoding="utf-8", errors="replace")
    total_available = engine.count_potential_mutations(original_code)

    if total_available == 0:
        return {
            "status": "NO_MUTATIONS_AVAILABLE",
            "message": "No mutable binary/comparison operators found; nothing to evolve.",
        }

    if not _run_test_command(test_command):
        return {
            "status": "BASELINE_TEST_FAILED",
            "message": "Test command must pass against the unmodified original before evolving it.",
        }

    baseline_time = measure_execution_speed(test_command, iterations=3)
    if baseline_time >= 999.0:
        return {"status": "BASELINE_FAILED", "message": "Baseline benchmark run failed."}

    backup_path = target_script.with_suffix(".py.bak")
    shutil.copy2(target_script, backup_path)

    trials = []
    best: Dict[str, Any] = {}
    try:
        for idx in range(min(total_available, max_mutants)):
            mutated_code, desc = engine.generate_mutant(original_code, idx)
            if mutated_code == original_code:
                trials.append({"mutant_id": idx + 1, "description": desc, "status": "NO_OP"})
                continue

            target_script.write_text(mutated_code, encoding="utf-8")
            tests_pass = _run_test_command(test_command)

            if not tests_pass:
                trials.append({"mutant_id": idx + 1, "description": desc, "status": "REJECTED_TEST_FAILED"})
                continue

            candidate_time = measure_execution_speed(test_command, iterations=3)
            speedup = ((baseline_time - candidate_time) / max(baseline_time, 0.001)) * 100.0
            trial = {
                "mutant_id": idx + 1,
                "description": desc,
                "status": "TESTS_PASSED",
                "candidate_time_sec": round(candidate_time, 4),
                "speedup_percent": round(speedup, 2),
            }
            trials.append(trial)

            if speedup > 0 and (not best or speedup > best.get("speedup_percent", 0)):
                best = {**trial, "mutated_code": mutated_code}
    finally:
        shutil.copy2(backup_path, target_script)
        backup_path.unlink(missing_ok=True)

    ratified = bool(best)
    result: Dict[str, Any] = {
        "status": "COMPLETED",
        "target": str(target_script),
        "baseline_time_sec": round(baseline_time, 4),
        "mutants_tried": len(trials),
        "trials": trials,
        "ratified_for_evolution": ratified,
    }
    if ratified:
        result["ratified_mutant"] = {
            "mutant_id": best["mutant_id"],
            "description": best["description"],
            "speedup_percent": best["speedup_percent"],
        }
        result["ratified_mutant_code"] = best["mutated_code"]
        result["message"] = (
            "A genuinely mutated, test-passing variant was faster. It is NOT applied automatically -- "
            "review 'ratified_mutant_code' and apply it manually if it looks correct."
        )
    else:
        result["message"] = "No available mutation both passed the tests and was faster than the original."

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Darwinian Self-Evolution & Optimization Engine (real AST mutants only)."
    )
    parser.add_argument("--target", "-t", required=True, help="Target script path to try to optimize.")
    parser.add_argument("--test-cmd", "-c", required=True, help="Validation test command.")
    parser.add_argument("--max-mutants", "-m", type=int, default=5, help="Number of mutants to try.")
    parser.add_argument("--output", "-o", default=None, help="Save report to JSON file.")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()
    result = run_evolution_cycle(target_path, args.test_cmd, max_mutants=args.max_mutants)

    output_str = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Evolution report saved to: {args.output}")
    else:
        print(output_str)

    return 0 if result.get("status") in ("COMPLETED", "NO_MUTATIONS_AVAILABLE") else 1


if __name__ == "__main__":
    sys.exit(main())
