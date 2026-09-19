"""
Unit and integration tests for Windows-Native Job Object Hardware Sandbox & Process Isolation.
Validates execution safety, wall-clock timeout killing, and memory limits.
"""

from __future__ import annotations

import sys
import pytest

from saleha.core.windows_job_sandbox import IS_WINDOWS, SandboxRunResult, WindowsJobSandbox


class TestWindowsJobSandbox:
    def setup_method(self) -> None:
        self.sandbox = WindowsJobSandbox(memory_limit_mb=50, timeout_ms=3000)

    def test_safe_execution_passes(self) -> None:
        code = "print('Hello Windows Sandbox'); x = 10 * 5; print(f'Output: {x}')"
        res = self.sandbox.run_isolated_python_snippet(code, timeout_sec=3.0)
        assert res.passed is True
        assert res.exit_code == 0
        assert "Output: 50" in res.output
        assert res.timed_out is False
        assert res.memory_limit_hit is False

    def test_runtime_exception_captured(self) -> None:
        code = "raise ZeroDivisionError('Intentional crash in sandbox')"
        res = self.sandbox.run_isolated_python_snippet(code, timeout_sec=2.0)
        assert res.passed is False
        assert res.exit_code != 0
        assert "ZeroDivisionError" in res.error

    def test_wall_clock_timeout_kills_infinite_loop(self) -> None:
        code = "import time\nwhile True: time.sleep(0.05)"
        res = self.sandbox.run_isolated_python_snippet(code, timeout_sec=0.3)
        assert res.passed is False
        assert res.timed_out is True
        assert "CRITICAL_TIMEOUT" in res.error

    def test_memory_limit_exhaustion_detected(self) -> None:
        # Create a sandbox with strict 15MB limit and attempt to allocate 100MB
        strict_sandbox = WindowsJobSandbox(memory_limit_mb=15, timeout_ms=3000)
        code = "data = bytearray(100 * 1024 * 1024); print(len(data))"
        res = strict_sandbox.run_isolated_python_snippet(code, timeout_sec=3.0)
        assert res.passed is False
        # Memory limit violation triggers memory_limit_hit (either via OS quota or MemoryError)
        assert res.memory_limit_hit is True or res.exit_code != 0

    def test_job_object_lifecycle_on_windows(self) -> None:
        if IS_WINDOWS:
            job = self.sandbox._create_job_object()
            assert job is not None
            import ctypes
            ctypes.windll.kernel32.CloseHandle(job)
        else:
            assert self.sandbox._create_job_object() is None
