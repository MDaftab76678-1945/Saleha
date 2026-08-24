"""
Saleha Core: Code Executor (Security-Hardened Version)
Generated code ko temporary file mein save karke automatically run karta hai.

Naya (security checklist se):
5. Import allowlist/blocklist -- AST se code ke saare imports padhta hai
   (regex se zyada bharosemand, kyunki string-matching bypass nahi kar
   sakta jaise "im" + "port socket" jaisi tricks).
6. Audit log -- har execution attempt (allowed ho ya blocked) record hoti
   hai ~/.saleha/audit_log.jsonl me.
7. Output size limit -- bahut zyada output (jaise accidental infinite
   print loop) ko cap karta hai, taaki terminal/memory flood na ho.

Pehle se:
1. python/python3 fallback
2. Configurable timeout
3. Cleanup failure logging
4. Pattern-based dangerous-code check (safety_patterns.py se)
"""

import subprocess
import tempfile
import os
import shutil
import sys
import ast
from dataclasses import dataclass
from typing import List, Optional

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from saleha.core.safety_patterns import (
    BLOCKED_IMPORTS,
    check_dangerous,
    _check_blocked_imports as _sp_check_blocked_imports,
)
from saleha.core.execution_policy import resolve_backend, build_docker_command, ensure_image
from saleha.core.audit_log import AuditLog


MAX_OUTPUT_CHARS = 50_000  # ~50KB -- itna kaafi hai normal script output ke liye


@dataclass
class ExecutionResult:
    success: bool
    output: str
    error: str
    exit_code: int
    cleanup_warning: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    output_truncated: bool = False
    backend: str = "subprocess"  # "subprocess" | "docker" | "none"


def _find_python_executable() -> Optional[str]:
    """python3 ko prefer karo (zyada systems pe consistent hai), fallback python."""
    for candidate in ("python3", "python"):
        path = shutil.which(candidate)
        if path:
            return candidate
    return None


def _check_blocked_imports(code: str) -> Optional[str]:
    """Single source of truth: safety_patterns._check_blocked_imports
    (static imports + dynamic __import__/importlib detection). Pehle yahan
    ek duplicate weaker copy thi jo sirf static statements dekhti thi."""
    return _sp_check_blocked_imports(code)


class CodeExecutor:
    def __init__(self, timeout: int = 30, audit: bool = True):
        self.timeout = timeout
        self.python_cmd = _find_python_executable()
        self.audit_log = AuditLog() if audit else None

    def _check_dangerous(self, code: str) -> Optional[str]:
        danger = check_dangerous(code)
        if danger:
            return f"{danger.description} (pattern: '{danger.pattern}')"
        return None

    def execute(
        self,
        code: str,
        timeout: Optional[int] = None,
        allow_dangerous: bool = False,
    ) -> ExecutionResult:
        """
        Python code ko execute karta hai aur output return karta hai.
        `timeout` diya jaye to constructor wale default ko override karta hai.
        """
        effective_timeout = timeout if timeout is not None else self.timeout

        if self.python_cmd is None:
            return ExecutionResult(
                success=False,
                output="",
                error="Neither 'python' nor 'python3' found on PATH. "
                      "Please ensure Python is installed and on PATH.",
                exit_code=-1,
            )

        if not allow_dangerous:
            reason = self._check_dangerous(code)
            if reason:
                if self.audit_log:
                    self.audit_log.record(code=code, allowed=False, reason=reason)
                return ExecutionResult(
                    success=False,
                    output="",
                    error="",
                    exit_code=-1,
                    blocked=True,
                    block_reason=reason,
                )

        # Temporary file create karein
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        # Execution policy: subprocess (legacy) vs hardened Docker sandbox.
        # Default "auto" = subprocess (backward-compatible). Strict mode
        # (SALEHA_SANDBOX=require-docker) me Docker na mile to fail-closed.
        backend, backend_reason = resolve_backend()
        if backend == "none":
            if self.audit_log:
                self.audit_log.record(code=code, allowed=False, reason=backend_reason)
            return ExecutionResult(
                success=False,
                output="",
                error=backend_reason,
                exit_code=-1,
                blocked=True,
                block_reason=backend_reason,
                backend="none",
            )

        cleanup_warning = None
        try:
            if backend == "docker":
                # Image preflight: absent ho to ek baar auto-pull (fail-fast
                # ki jagah graceful), warna clear error message.
                image_ok, image_msg = ensure_image()
                if not image_ok:
                    reason = f"Docker sandbox image unavailable: {image_msg}"
                    if self.audit_log:
                        self.audit_log.record(code=code, allowed=False, reason=reason)
                    return ExecutionResult(
                        success=False,
                        output="",
                        error=reason,
                        exit_code=-1,
                        blocked=True,
                        block_reason=reason,
                        backend="none",
                    )
            run_cmd = (
                build_docker_command(temp_file)
                if backend == "docker"
                else [self.python_cmd, temp_file]
            )
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=os.path.dirname(temp_file),
            )

            output = result.stdout
            error = result.stderr
            truncated = False
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS] + "\n...[output truncated]..."
                truncated = True
            if len(error) > MAX_OUTPUT_CHARS:
                error = error[:MAX_OUTPUT_CHARS] + "\n...[error truncated]..."
                truncated = True

            exec_success = result.returncode == 0
            if self.audit_log:
                self.audit_log.record(
                    code=code,
                    allowed=True,
                    reason=f"backend={backend}; {backend_reason}",
                    executed=True,
                    success=exec_success,
                    exit_code=result.returncode,
                )

            return ExecutionResult(
                success=exec_success,
                output=output,
                error=error,
                exit_code=result.returncode,
                output_truncated=truncated,
                backend=backend,
            )

        except subprocess.TimeoutExpired:
            timeout_error = f"Code execution timed out after {effective_timeout} seconds"
            if self.audit_log:
                self.audit_log.record(
                    code=code, allowed=True, reason=f"backend={backend}; {timeout_error}",
                    executed=True, success=False, exit_code=-1,
                )
            return ExecutionResult(
                success=False,
                output="",
                error=timeout_error,
                exit_code=-1,
                backend=backend,
            )
        except (subprocess.SubprocessError, OSError) as e:
            if self.audit_log:
                self.audit_log.record(
                    code=code, allowed=True, reason=str(e),
                    executed=True, success=False, exit_code=-1,
                )
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                backend=backend,
            )
        finally:
            try:
                os.unlink(temp_file)
            except Exception as cleanup_err:
                cleanup_warning = f"Temp file cleanup failed: {cleanup_err}"
                print(f"[CodeExecutor] warning: {cleanup_warning}")


if __name__ == "__main__":
    print("Code Executor Test (Security-Hardened Version)")
    executor = CodeExecutor()
    print(f"Using interpreter: {executor.python_cmd}")

    test_code = """
def hello():
    print("Hello from Saleha!")

hello()
print("Execution successful!")
"""

    result = executor.execute(test_code)
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    if result.error:
        print(f"Error: {result.error}")

    # Pattern-based check test
    dangerous_code = "import shutil\nshutil.rmtree('/')\n"
    blocked_result = executor.execute(dangerous_code)
    print(f"\nBlocked (pattern): {blocked_result.blocked}, reason: {blocked_result.block_reason}")

    # Import-allowlist check test
    network_code = "import socket\ns = socket.socket()\n"
    blocked_result2 = executor.execute(network_code)
    print(f"Blocked (import): {blocked_result2.blocked}, reason: {blocked_result2.block_reason}")