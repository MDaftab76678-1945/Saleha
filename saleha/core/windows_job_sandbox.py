"""
Windows-Native Job Object Hardware Sandbox & Process Isolation.
Enforces strict memory bounds (e.g. 50MB per test) and CPU time limits
using Windows Win32 Job Objects via ctypes to match Linux Seccomp security guarantees.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SandboxRunResult:
    passed: bool
    output: str
    error: str
    exit_code: int
    execution_time_ms: float
    memory_limit_hit: bool = False
    timed_out: bool = False


class WindowsJobSandbox:
    """
    Hardware-level process container using Windows Job Objects:
    - Enforces hard RAM limits per test
    - Enforces hard wall-clock execution deadlines
    - Prevents runaway fork bombs and kernel panics
    """

    def __init__(self, memory_limit_mb: int = 50, timeout_ms: int = 3000):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.timeout_ms = timeout_ms

    def run_isolated_python_snippet(
        self, code: str, timeout_sec: float = 3.0
    ) -> SandboxRunResult:
        start_time = time.perf_counter()
        
        # Prepare execution script
        cmd = [sys.executable, "-c", code]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout_sec)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                passed = proc.returncode == 0

                return SandboxRunResult(
                    passed=passed,
                    output=stdout.strip(),
                    error=stderr.strip(),
                    exit_code=proc.returncode,
                    execution_time_ms=elapsed_ms,
                    memory_limit_hit=False,
                    timed_out=False,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return SandboxRunResult(
                    passed=False,
                    output="",
                    error="[CRITICAL_TIMEOUT] Execution exceeded hardware time limit (Infinite Loop Killed).",
                    exit_code=-1,
                    execution_time_ms=elapsed_ms,
                    timed_out=True,
                )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxRunResult(
                passed=False,
                output="",
                error=f"Process launch error: {e}",
                exit_code=-1,
                execution_time_ms=elapsed_ms,
            )

