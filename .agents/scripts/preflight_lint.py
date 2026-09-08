#!/usr/bin/env python3
"""Saleha Pre-Flight Quality & Missing-Import Gate.

Scans modified or target Python files using Saleha's AST QualityGuard to catch
undefined names, missing imports, syntax errors, and anti-patterns BEFORE commit.
Exits with 0 if all clean, 1 if any critical/major defect is detected.
"""

from __future__ import annotations

import os
import sys
import argparse

# Add repo root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from saleha.core.quality_guard import QualityGuard


def main() -> int:
    parser = argparse.ArgumentParser(description="Saleha AST Pre-Flight Quality Gate")
    parser.add_argument("files", nargs="*", help="Python files to check")
    parser.add_argument("--all-core", action="store_true", help="Check all core and tool modules")
    args = parser.parse_args()

    files_to_check = []
    if args.files:
        files_to_check = [f for f in args.files if f.endswith(".py") and os.path.exists(f)]
    elif args.all_core:
        for folder in ["saleha/core", "saleha/tools"]:
            folder_path = os.path.join(REPO_ROOT, folder)
            if os.path.exists(folder_path):
                for f in os.listdir(folder_path):
                    if f.endswith(".py"):
                        files_to_check.append(os.path.join(folder_path, f))
    else:
        # Default: check git staged or modified files
        import subprocess
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        if proc.returncode == 0 and proc.stdout:
            for line in proc.stdout.splitlines():
                f = line.strip()
                if f.endswith(".py") and os.path.exists(os.path.join(REPO_ROOT, f)):
                    files_to_check.append(os.path.join(REPO_ROOT, f))

    if not files_to_check:
        print("[preflight] No Python files to verify.")
        return 0

    guard = QualityGuard(strict_mode=True)
    has_failure = False

    print(f"[preflight] Scanning {len(files_to_check)} file(s) for syntax, missing imports, and quality...")
    for fpath in files_to_check:
        report = guard.check_file(fpath)
        rel_path = os.path.relpath(fpath, REPO_ROOT)
        if not report.passed:
            has_failure = True
            print(f"\n[FAIL] {rel_path} (Score: {report.quality_score}/100)")
            for issue in report.issues:
                if issue.severity in ("CRITICAL", "MAJOR"):
                    print(f"  Line {issue.line_number}:{issue.column} [{issue.severity} {issue.rule_id}] {issue.message}")
        else:
            print(f"  [PASS] {rel_path} (Score: {report.quality_score}/100)")

    if has_failure:
        print("\n[BLOCKED] Pre-flight quality gate failed. Fix all issues before proceeding.")
        return 1

    print("\n[SUCCESS] All files passed pre-flight AST verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
