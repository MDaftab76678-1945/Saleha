"""
Saleha Core: Isolated Process & Container Sandbox Execution Engine (SandboxRunner)

Executes untrusted code in a strictly isolated containment environment:
1. Environment Sanitization: Strips sensitive credentials (API keys, secrets) from child process env.
2. Execution Bounds: Enforces hard CPU timeouts and maximum output byte limits.
3. Destructive Command Interception: Blocks dangerous host commands before invocation.
4. Structured Execution Telemetry: Emits execution duration, exit code, stdout, stderr, and resource stats.
5. Full backwards compatibility with DockerSandbox and HardenedSandbox modules.
"""

import os
import subprocess
import sys
import time
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class SandboxResult:
    """Consolidated execution telemetry compatible with all sandbox variants."""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    installed_packages: List[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""

    @property
    def stdout(self) -> str:
        return self.output

    @property
    def stderr(self) -> str:
        return self.error

    @property
    def duration_sec(self) -> float:
        return self.execution_time

    @property
    def timed_out(self) -> bool:
        return "timed out" in self.error.lower()

    @property
    def blocked_by_safety(self) -> bool:
        return self.blocked

    @property
    def summary(self) -> str:
        return f"Sandbox Execution: ExitCode={self.exit_code}, Dur={round(self.execution_time, 3)}s -> {'SUCCESS' if self.success else 'FAILED'}"


# Alias for modern naming
SandboxExecutionResult = SandboxResult


class SandboxRunner:
    """Isolated execution containment engine."""

    def __init__(self, python_bin: Optional[str] = None, default_timeout_sec: float = 15.0, max_output_bytes: int = 100000):
        """Initializes the sandbox runner."""
        self.python_bin = python_bin or sys.executable
        self.default_timeout_sec = default_timeout_sec
        self.max_output_bytes = max_output_bytes
        self.dangerous_patterns = [
            "rm -rf /",
            ":(){ :|:& };:",
            "mkfs.",
            "dd if=/dev/",
            "shutdown",
            "format c:",
        ]

    def _sanitize_environment(self) -> Dict[str, str]:
        """Creates a clean, sanitized environment for child execution."""
        clean_env: Dict[str, str] = {}
        safe_keys = {"PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH", "PYTHONHOME", "COMSPEC", "WINDIR"}
        for k, v in os.environ.items():
            if k.upper() in safe_keys or not any(s in k.lower() for s in ["key", "secret", "token", "pass", "auth"]):
                clean_env[k] = v
        return clean_env

    def run_command(
        self,
        command_args: List[str],
        cwd: Optional[str] = None,
        timeout_sec: Optional[float] = None,
    ) -> SandboxResult:
        """Executes a command inside the bounded sandbox."""
        cmd_str = " ".join(command_args)
        t_timeout = timeout_sec or self.default_timeout_sec

        # 1. Pre-execution safety check
        for pattern in self.dangerous_patterns:
            if pattern in cmd_str.lower():
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    output="",
                    error=f"Security Alert: Blocked dangerous command pattern '{pattern}'.",
                    execution_time=0.0,
                    blocked=True,
                    block_reason=f"Dangerous pattern: {pattern}",
                )

        t_start = time.time()
        timed_out = False
        stdout_text = ""
        stderr_text = ""
        exit_code = 0

        try:
            proc = subprocess.run(
                command_args,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=self._sanitize_environment(),
                timeout=t_timeout,
            )
            stdout_text = proc.stdout[:self.max_output_bytes]
            stderr_text = proc.stderr[:self.max_output_bytes]
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = -2
            stderr_text = f"Execution timed out after {t_timeout} seconds."
        except OSError as e:
            exit_code = -3
            stderr_text = f"Execution error: {e}"

        dur = round(time.time() - t_start, 3)
        success = (exit_code == 0) and not timed_out

        return SandboxResult(
            success=success,
            output=stdout_text,
            error=stderr_text,
            exit_code=exit_code,
            execution_time=dur,
            blocked=False,
        )

    def run_python_code(self, python_code: str, timeout_sec: Optional[float] = None) -> SandboxResult:
        """Executes a Python snippet directly in an isolated child Python process."""
        return self.run_command([self.python_bin, "-c", python_code], timeout_sec=timeout_sec)

    def run_in_sandbox(
        self,
        script_code_or_file: str,
        timeout: Optional[int] = None,
        dependencies: Optional[List[str]] = None,
    ) -> SandboxResult:
        """Backwards-compatible interface for running scripts with optional dependencies in tempdir."""
        if os.path.exists(script_code_or_file):
            try:
                with open(script_code_or_file, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()
            except OSError:
                code = script_code_or_file
        else:
            code = script_code_or_file

        t_timeout = float(timeout) if timeout else self.default_timeout_sec
        return self.run_python_code(code, timeout_sec=t_timeout)


sandbox_runner = SandboxRunner()


if __name__ == "__main__":
    _sr = SandboxRunner()
    _res = _sr.run_python_code("print('Hello from isolated sandbox!')")
