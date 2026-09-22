#!/usr/bin/env python3
"""Saleha Pre-Flight Quality & Missing-Import Gate.

Scans modified or target Python files using Saleha's AST QualityGuard to catch
undefined names, missing imports, syntax errors, and anti-patterns BEFORE commit.
Also checks that the audit ledger and CLAUDE.md have not drifted apart.
Exits with 0 if all clean, 1 if any critical/major defect is detected.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import List, Optional, Set

# Add repo root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from saleha.core.verification.quality_guard import QualityGuard


def _list_py_files(folder_path: str) -> List[str]:
    """Returns absolute paths of all .py files inside folder_path (recursively)."""
    if not os.path.exists(folder_path):
        return []
    py_files: List[str] = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for f in sorted(files):
            if f.endswith(".py"):
                py_files.append(os.path.abspath(os.path.join(root, f)))
    return py_files


def _git_modified_py_files() -> List[str]:
    """Returns absolute paths of .py files git reports as modified or untracked since HEAD."""
    file_rel_paths: Set[str] = set()

    # Tracked modified/staged files
    proc_diff = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc_diff.returncode == 0 and proc_diff.stdout:
        for line in proc_diff.stdout.splitlines():
            stripped = line.strip()
            if stripped:
                file_rel_paths.add(stripped)

    # Untracked files (new files not yet staged or committed)
    proc_untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc_untracked.returncode == 0 and proc_untracked.stdout:
        for line in proc_untracked.stdout.splitlines():
            stripped = line.strip()
            if stripped:
                file_rel_paths.add(stripped)

    result: List[str] = []
    for rel_f in sorted(file_rel_paths):
        if rel_f.endswith(".py"):
            full_path = os.path.abspath(os.path.join(REPO_ROOT, rel_f))
            if os.path.isfile(full_path):
                result.append(full_path)
    return result


def _collect_files_to_check(explicit_files: List[str], all_core: bool) -> List[str]:
    """Resolves which files to scan: explicit args > --all-core > git diff."""
    if explicit_files:
        collected: List[str] = []
        for f in explicit_files:
            abs_p = os.path.abspath(f)
            if abs_p.endswith(".py") and os.path.isfile(abs_p):
                collected.append(abs_p)
        return collected

    if all_core:
        files: List[str] = []
        for folder in ("saleha/core", "saleha/tools"):
            files.extend(_list_py_files(os.path.join(REPO_ROOT, folder)))
        return files

    return _git_modified_py_files()


def _scan_and_report(files_to_check: List[str], guard: QualityGuard) -> bool:
    """Runs QualityGuard over every file and prints a PASS/FAIL line for each.

    Returns True if at least one file failed.
    """
    has_failure = False
    for fpath in files_to_check:
        report = guard.check_file(fpath)
        rel_path = os.path.relpath(fpath, REPO_ROOT)
        if report.passed:
            print(f"  [PASS] {rel_path} (Score: {report.quality_score}/100)")
            continue

        has_failure = True
        print(f"\n[FAIL] {rel_path} (Score: {report.quality_score}/100)")
        has_critical_or_major = False
        for issue in report.issues:
            if issue.severity in ("CRITICAL", "MAJOR"):
                has_critical_or_major = True
                print(f"  Line {issue.line_number}:{issue.column} [{issue.severity} {issue.rule_id}] {issue.message}")

        if not has_critical_or_major:
            print(f"  Score fell below threshold (Score: {report.quality_score} < 70.0). Minor issues:")
            for issue in report.issues[:10]:
                print(f"  Line {issue.line_number}:{issue.column} [{issue.severity} {issue.rule_id}] {issue.message}")
            if len(report.issues) > 10:
                print(f"  ... and {len(report.issues) - 10} more minor issue(s)")

    return has_failure


def _highest_pass_number(file_path: str) -> Optional[int]:
    """Returns the highest 'Pass N' / 'passes N-M' number mentioned in a file.

    Returns None if the file is absent or names no pass at all, so a missing
    file is reported as unknown rather than silently treated as up to date.
    """
    if not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None

    numbers = [int(n) for n in re.findall(r"[Pp]ass(?:es)?\s+(\d{1,4})", text)]
    numbers += [int(n) for n in re.findall(r"[Pp]asses\s+\d{1,4}\s*[-–]\s*(\d{1,4})", text)]
    return max(numbers) if numbers else None


def check_ledger_sync() -> bool:
    """Blocks a commit when NOTEBOOK_IMPORT.md records passes CLAUDE.md does not.

    CLAUDE.md is the only file loaded automatically at session start, so a pass
    recorded solely in the ledger is invisible to the next session -- the exact
    drift that left passes 66-80 and 140-147 unrecorded there. Returns True on
    failure, matching _scan_and_report's convention.
    """
    ledger_path = os.path.join(REPO_ROOT, "NOTEBOOK_IMPORT.md")
    claude_path = os.path.join(REPO_ROOT, "CLAUDE.md")

    ledger_pass = _highest_pass_number(ledger_path)
    claude_pass = _highest_pass_number(claude_path)

    if ledger_pass is None or claude_pass is None:
        print("[preflight] Ledger sync check skipped: CLAUDE.md or NOTEBOOK_IMPORT.md not readable.")
        return False

    if ledger_pass > claude_pass:
        print("\n[FAIL] Audit ledger and CLAUDE.md have drifted apart.")
        print(f"  NOTEBOOK_IMPORT.md records up to pass {ledger_pass}")
        print(f"  CLAUDE.md records up to pass {claude_pass}")
        print("  CLAUDE.md is the only file auto-loaded at session start, so passes")
        print("  recorded only in the ledger are invisible to the next session.")
        print(f"  Add a short summary of pass {claude_pass + 1}-{ledger_pass} to CLAUDE.md.")
        return True

    print(f"[preflight] Ledger sync OK (CLAUDE.md pass {claude_pass} >= ledger pass {ledger_pass}).")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Saleha AST Pre-Flight Quality Gate")
    parser.add_argument("files", nargs="*", help="Python files to check")
    parser.add_argument("--all-core", action="store_true", help="Check all core and tool modules")
    parser.add_argument(
        "--skip-ledger-check",
        action="store_true",
        help="Skip the CLAUDE.md/NOTEBOOK_IMPORT.md drift check.",
    )
    args = parser.parse_args()

    # Runs even when no Python file changed: a docs-only commit is exactly when
    # the ledger tends to move without CLAUDE.md following it.
    ledger_drifted = False if args.skip_ledger_check else check_ledger_sync()

    files_to_check = _collect_files_to_check(args.files, args.all_core)
    if not files_to_check:
        print("[preflight] No Python files to verify.")
        if ledger_drifted:
            print("\n[BLOCKED] Pre-flight gate failed. Fix all issues before proceeding.")
            return 1
        return 0

    print(f"[preflight] Scanning {len(files_to_check)} file(s) for syntax, missing imports, and quality...")
    guard = QualityGuard(strict_mode=True)
    has_failure = _scan_and_report(files_to_check, guard)

    if has_failure or ledger_drifted:
        print("\n[BLOCKED] Pre-flight gate failed. Fix all issues before proceeding.")
        return 1

    print("\n[SUCCESS] All files passed pre-flight AST verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
