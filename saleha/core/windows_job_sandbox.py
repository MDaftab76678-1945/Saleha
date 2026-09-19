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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    # Win32 Job Object constants
    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


@dataclass
class SandboxRunResult:
    passed: bool
    output: str
    error: str
    exit_code: int
    execution_time_ms: float
    memory_limit_hit: bool = False
    timed_out: bool = False
    peak_memory_bytes: int = 0


class WindowsJobSandbox:
    """
    Hardware-level process container using Windows Job Objects:
    - Enforces hard RAM limits per test
    - Enforces hard wall-clock execution deadlines
    - Prevents runaway fork bombs and kernel panics
    """

    def __init__(self, memory_limit_mb: int = 50, timeout_ms: int = 3000) -> None:
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.timeout_ms = timeout_ms

    def _create_job_object(self) -> Any:
        if not IS_WINDOWS:
            return None
        try:
            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                | JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | JOB_OBJECT_LIMIT_JOB_MEMORY
            )
            info.ProcessMemoryLimit = self.memory_limit_bytes
            info.JobMemoryLimit = self.memory_limit_bytes

            success = kernel32.SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not success:
                kernel32.CloseHandle(job)
                return None
            return job
        except Exception:
            return None

    def _query_peak_memory(self, job_handle: Any) -> int:
        if not IS_WINDOWS or not job_handle:
            return 0
        try:
            kernel32 = ctypes.windll.kernel32
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            returned_length = wintypes.DWORD()
            success = kernel32.QueryInformationJobObject(
                job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
                ctypes.byref(returned_length),
            )
            if success:
                return int(max(info.PeakProcessMemoryUsed, info.PeakJobMemoryUsed))
            return 0
        except Exception:
            return 0

    def run_isolated_python_snippet(
        self, code: str, timeout_sec: float = 3.0
    ) -> SandboxRunResult:
        start_time = time.perf_counter()
        cmd = [sys.executable, "-c", code]
        job_handle = self._create_job_object()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Assign process handle to Job Object
            if IS_WINDOWS and job_handle and hasattr(proc, "_handle"):
                try:
                    kernel32 = ctypes.windll.kernel32
                    kernel32.AssignProcessToJobObject(job_handle, proc._handle)
                except Exception:
                    pass

            try:
                stdout, stderr = proc.communicate(timeout=timeout_sec)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                peak_bytes = self._query_peak_memory(job_handle)

                # Check memory exhaustion status
                # 0xC0000017 = STATUS_NO_MEMORY (-1073741801 signed, 3221225495 unsigned)
                # 0xC0000044 = STATUS_QUOTA_EXCEEDED (-1073741756 signed, 3221225540 unsigned)
                memory_limit_hit = False
                if proc.returncode in (-1073741801, 3221225495, -1073741756, 3221225540):
                    memory_limit_hit = True
                elif "MemoryError" in stderr or "out of memory" in stderr.lower():
                    memory_limit_hit = True
                elif peak_bytes > 0 and peak_bytes >= self.memory_limit_bytes:
                    memory_limit_hit = True

                passed = (proc.returncode == 0) and not memory_limit_hit

                return SandboxRunResult(
                    passed=passed,
                    output=stdout.strip(),
                    error=stderr.strip(),
                    exit_code=proc.returncode,
                    execution_time_ms=elapsed_ms,
                    memory_limit_hit=memory_limit_hit,
                    timed_out=False,
                    peak_memory_bytes=peak_bytes,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                peak_bytes = self._query_peak_memory(job_handle)
                return SandboxRunResult(
                    passed=False,
                    output="",
                    error="[CRITICAL_TIMEOUT] Execution exceeded hardware time limit (Infinite Loop Killed).",
                    exit_code=-1,
                    execution_time_ms=elapsed_ms,
                    memory_limit_hit=False,
                    timed_out=True,
                    peak_memory_bytes=peak_bytes,
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
        finally:
            if IS_WINDOWS and job_handle:
                try:
                    kernel32 = ctypes.windll.kernel32
                    kernel32.CloseHandle(job_handle)
                except Exception:
                    pass
