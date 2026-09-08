#!/usr/bin/env python3
"""Saleha Pre-Flight Quality & Missing-Import Gate.

Scans modified or target Python files using Saleha's AST QualityGuard to catch
undefined names, missing imports, syntax errors, and anti-patterns BEFORE commit.
Exits with 0 if all clean, 1 if any critical/major defect is detected.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List

# Add repo root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from saleha.core.quality_guard import QualityGuard


def _list_py_files(folder_path: str) -> List[str]:
    """Returns absolute paths of every .py file directly inside folder_path."""
    if not os.path.exists(folder_path):
        return []
    return [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.endswith(".py")
    ]


def _git_modified_py_files() -> List[str]:
    """Returns absolute paths of .py files git reports as modified since HEAD."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return []

    candidates = (line.strip() for line in proc.stdout.splitlines())
    return [
        os.path.join(REPO_ROOT, f)
        for f in candidates
        if f.endswith(".py") and os.path.exists(os.path.join(REPO_ROOT, f))
    ]


def _collect_files_to_check(explicit_files: List[str], all_core: bool) -> List[str]:
    """Resolves which files to scan: explicit args > --all-core > git diff."""
    if explicit_files:
        return [f for f in explicit_files if f.endswith(".py") and os.path.exists(f)]

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
        for issue in report.issues:
            if issue.severity in ("CRITICAL", "MAJOR"):
                print(f"  Line {issue.line_number}:{issue.column} [{issue.severity} {issue.rule_id}] {issue.message}")

    return has_failure


def main() -> int:
    parser = argparse.ArgumentParser(description="Saleha AST Pre-Flight Quality Gate")
    parser.add_argument("files", nargs="*", help="Python files to check")
    parser.add_argument("--all-core", action="store_true", help="Check all core and tool modules")
    args = parser.parse_args()

    files_to_check = _collect_files_to_check(args.files, args.all_core)
    if not files_to_check:
        print("[preflight] No Python files to verify.")
        return 0

    print(f"[preflight] Scanning {len(files_to_check)} file(s) for syntax, missing imports, and quality...")
    guard = QualityGuard(strict_mode=True)
    has_failure = _scan_and_report(files_to_check, guard)

    if has_failure:
        print("\n[BLOCKED] Pre-flight quality gate failed. Fix all issues before proceeding.")
        return 1

    print("\n[SUCCESS] All files passed pre-flight AST verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
