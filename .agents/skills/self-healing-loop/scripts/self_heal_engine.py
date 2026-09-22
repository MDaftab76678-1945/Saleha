#!/usr/bin/env python3
"""Self-Healing Diagnosis and Surgical Repair Engine.

Parses runtime/test tracebacks, pinpoints the root cause down to exact AST line
coordinates, and assists in generating and verifying isolated surgical fixes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

REPO_ROOT = Path(__file__).resolve().parents[4]


def parse_python_traceback(stderr_text: str) -> List[Dict[str, Any]]:
    """Extracts all traceback frames with file, line, function, and code snippet."""
    frame_pattern = re.compile(
        r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\w+)\n(?:\s+(?P<code>.+))?'
    )
    frames: List[Dict[str, Any]] = []

    for match in frame_pattern.finditer(stderr_text):
        frames.append(
            {
                "file": match.group("file").replace("\\", "/"),
                "line": int(match.group("line")),
                "function": match.group("func"),
                "code": match.group("code").strip() if match.group("code") else "",
            }
        )

    return frames


def extract_exception_details(output_text: str) -> Dict[str, str]:
    """Finds the trailing exception class and error message in terminal output."""
    exc_pattern = re.compile(r"^([A-Z]\w*(?:Error|Exception|Exit)): (.+)$", re.MULTILINE)
    matches = list(exc_pattern.finditer(output_text))
    if matches:
        last = matches[-1]
        return {"type": last.group(1), "message": last.group(2).strip()}
    return {"type": "UnknownException", "message": "Could not parse exception string"}


def diagnose_failure(test_command: str) -> Dict[str, Any]:
    """Executes test_command, catches errors, and extracts surgical repair target."""
    proc = subprocess.run(
        test_command,
        shell=True,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if proc.returncode == 0:
        return {
            "status": "PASSED",
            "message": "Test execution succeeded with exit code 0. No healing required.",
            "returncode": 0,
        }

    combined_output = proc.stdout + "\n" + proc.stderr
    frames = parse_python_traceback(combined_output)
    exc = extract_exception_details(combined_output)

    # Filter frames to only repo-internal files
    repo_frames = [f for f in frames if "site-packages" not in f["file"] and not f["file"].startswith("<")]
    target_frame = repo_frames[-1] if repo_frames else (frames[-1] if frames else None)

    diagnosis = {
        "status": "FAILED",
        "returncode": proc.returncode,
        "exception_type": exc["type"],
        "exception_message": exc["message"],
        "target_frame": target_frame,
        "all_repo_frames": repo_frames,
    }

    if target_frame:
        target_file = Path(target_frame["file"])
        if target_file.exists():
            lines = target_file.read_text(encoding="utf-8", errors="replace").splitlines()
            target_line = target_frame["line"]
            start_ctx = max(0, target_line - 5)
            end_ctx = min(len(lines), target_line + 5)
            diagnosis["context_window"] = [
                f"{i + 1:4d}: {lines[i]}" for i in range(start_ctx, end_ctx)
            ]

    return diagnosis


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose test failures and isolate surgical healing targets."
    )
    parser.add_argument("--test-cmd", "-c", required=True, help="Test command to diagnose.")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path.")

    args = parser.parse_args()
    result = diagnose_failure(args.test_cmd)

    output_str = json.dumps(result, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Diagnosis written to: {out_path}")
    else:
        print(output_str)

    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
