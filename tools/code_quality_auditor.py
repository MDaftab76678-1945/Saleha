"""Saleha code quality and security SAST auditor."""

import ast
import glob
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class QualityMetric:
    total_python_files: int = 0
    total_lines_of_code: int = 0
    syntax_ast_errors: int = 0
    security_vulnerabilities: int = 0
    circular_imports: int = 0
    pep_typing_conformance: float = 100.0


def audit_repository() -> Dict[str, Any]:
    py_files = glob.glob("saleha/**/*.py", recursive=True)
    total_lines = 0
    ast_errors = []
    security_issues = []

    for f in py_files:
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                code = fp.read()
                total_lines += len(code.splitlines())
                ast.parse(code, filename=f)

                # Security Checks
                if "os.system(" in code:
                    security_issues.append((f, "Insecure os.system call"))
                if re.search(r"(?i)(api_key|password)\s*=\s*['\"][A-Za-z0-9_\-]{24,}['\"]", code):
                    if "test" not in f and "mock" not in f:
                        security_issues.append((f, "Hardcoded Secret"))

        except Exception as e:
            ast_errors.append((f, str(e)))

    return {
        "files_scanned": len(py_files),
        "lines_of_code": total_lines,
        "ast_clean": len(ast_errors) == 0,
        "ast_errors": ast_errors,
        "security_clean": len(security_issues) == 0,
        "security_issues": security_issues,
    }


def run_test_suite() -> Dict[str, Any]:
    """Runs the real pytest suite and reports what actually happened.

    Never returns a pass/fail claim without having executed pytest.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "saleha/tests/", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=900,
        )
    except FileNotFoundError as e:
        return {"ran": False, "reason": f"pytest not available: {e}"}
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "pytest timed out after 900s"}

    return {
        "ran": True,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "summary_tail": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "",
        "stderr_tail": proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "",
    }


if __name__ == "__main__":
    res = audit_repository()
    print("=" * 60)
    print("SALEHA CODE QUALITY REPORT")
    print("=" * 60)
    print(f"Python Modules Scanned    : {res['files_scanned']}")
    print(f"Total Lines of Code (LOC) : {res['lines_of_code']:,}")
    ast_status = "CLEAN (0 errors)" if res["ast_clean"] else f"{len(res['ast_errors'])} error(s) found"
    print(f"AST Syntax Correctness    : {ast_status}")
    if res["ast_errors"]:
        for f, err in res["ast_errors"]:
            print(f"    - [{err}] {f}")
    sec_status = "CLEAN (0 findings)" if res["security_clean"] else f"{len(res['security_issues'])} finding(s)"
    print(f"SAST Security Scan        : {sec_status}")
    if res["security_issues"]:
        for f, iss in res["security_issues"]:
            print(f"    - [{iss}] {f}")

    test_res = run_test_suite()
    if not test_res["ran"]:
        print(f"Test Suite                : NOT RUN ({test_res['reason']})")
    elif test_res["passed"]:
        print(f"Test Suite                : PASSED ({test_res['summary_tail']})")
    else:
        print(f"Test Suite                : FAILED ({test_res['summary_tail']})")
        if test_res["stderr_tail"]:
            print(f"    stderr: {test_res['stderr_tail']}")
    print("=" * 60)
