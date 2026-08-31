"""
Saleha CI: PyTest Runner with GitHub Actions Annotations and Step Summary

Runs the full test suite, captures all output, extracts failed test cases,
emits GitHub Actions workflow command annotations (::error), and appends
a formatted failure summary to $GITHUB_STEP_SUMMARY.
"""

from __future__ import annotations

import os
import sys
import subprocess
import re


def main():
    print(f"=== Saleha CI Test Runner on {sys.platform} (Python {sys.version.split()[0]}) ===")
    
    cmd = [
        sys.executable, "-m", "pytest", "saleha/tests",
        "-v", "--tb=short", "-p", "no:warnings"
    ]
    
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=dict(os.environ, PYTHONUNBUFFERED="1", OBJC_DISABLE_INITIALIZE_FORK_SAFETY="YES")
    )
    
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = stdout + "\n" + stderr
    
    print(stdout)
    if stderr:
        print("STDERR:\n" + stderr, file=sys.stderr)
        
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    
    if proc.returncode != 0:
        print(f"\n❌ PyTest exited with return code {proc.returncode}")
        
        # Extract failed tests: e.g. "FAILED saleha/tests/test_foo.py::TestClass::test_method - AssertionError: ..."
        failures = re.findall(r"FAILED\s+([^\s]+)\s*(?:-\s*(.*))?", combined)
        
        # Emit GitHub Actions workflow commands
        for f_name, reason in failures:
            print(f"::error title=Test Failure::{f_name} - {reason or 'Failed'}")
            
        if summary_file:
            try:
                with open(summary_file, "a", encoding="utf-8") as f:
                    f.write(f"\n### ❌ Test Failures on `{sys.platform}` (Python `{sys.version.split()[0]}`)\n\n")
                    f.write(f"**Total Failures:** {len(failures)}\n\n")
                    f.write("| Failed Test | Error Reason |\n|---|---|\n")
                    for f_name, reason in failures:
                        f.write(f"| `{f_name}` | {reason or 'Failed'} |\n")
                    f.write("\n<details><summary>Click to view pytest failure tracebacks</summary>\n\n```\n")
                    # Write failure sections from combined output
                    fail_section = combined[combined.find("FAILURES"):] if "FAILURES" in combined else combined[-3000:]
                    f.write(fail_section[:5000])
                    f.write("\n```\n</details>\n")
            except Exception as e:
                print(f"Warning: could not write to GITHUB_STEP_SUMMARY: {e}")
    else:
        print("\n✅ All tests passed successfully!")
        if summary_file:
            try:
                with open(summary_file, "a", encoding="utf-8") as f:
                    f.write(f"\n### ✅ All tests passed on `{sys.platform}` (Python `{sys.version.split()[0]}`)\n")
            except Exception:
                pass
                
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
