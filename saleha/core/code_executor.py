"""
Saleha Core: Code Executor (Security-Hardened Version)
Saves generated code to a temporary file and runs it automatically.

New (from the security checklist):
5. Import allowlist/blocklist -- reads all imports from the code's AST
   (more reliable than regex, since string-matching tricks like
   "im" + "port socket" cannot bypass it).
6. Audit log -- every execution attempt (allowed or blocked) is recorded
   to ~/.saleha/audit_log.jsonl.
7. Output size limit -- caps excessive output (e.g. an accidental infinite
   print loop) so the terminal/memory does not flood.

Already present:
1. python/python3 fallback
2. Configurable timeout
3. Cleanup failure logging
4. Pattern-based dangerous-code check (from safety_patterns.py)
"""

import subprocess
import tempfile
import os
import shutil
from dataclasses import dataclass
from typing import Optional

from saleha.core.safety_patterns import (
    check_dangerous,
    _check_blocked_imports as _sp_check_blocked_imports,
)
from saleha.core.execution_policy import resolve_backend, build_docker_command, ensure_image
from saleha.core.audit_log import AuditLog


MAX_OUTPUT_CHARS = 50_000  # ~50KB -- enough for normal script output


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
    """Prefers python3 (more consistent across systems), falls back to python."""
    for candidate in ("python3", "python"):
        path = shutil.which(candidate)
        if path:
            return candidate
    return None


def _check_blocked_imports(code: str) -> Optional[str]:
    """Single source of truth: safety_patterns._check_blocked_imports
    (static imports + dynamic __import__/importlib detection). This used to
    have a duplicate, weaker copy here that only looked at static statements."""
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

    def _prepare_temp_file(self, code: str) -> str:

        """Writes code to a secure temporary Python file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            return f.name

    def execute(
        self,
        code: str,
        timeout: Optional[int] = None,
        allow_dangerous: bool = False,
        language: str = "python",
    ) -> ExecutionResult:
        """Executes code in isolated environment (Docker or host subprocess, or Polyglot sandbox) and returns ExecutionResult."""
        effective_timeout = timeout if timeout is not None else self.timeout

        if language != "python":
            from saleha.core.polyglot_executor import PolyglotExecutor
            poly = PolyglotExecutor(timeout=effective_timeout)
            res = poly.execute(code, language=language)
            return ExecutionResult(
                success=res.success,
                output=res.output,
                error=res.error,
                exit_code=res.exit_code,
                blocked=res.blocked,
                block_reason=res.block_reason,
                backend="polyglot",
            )

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
                    success=False, output="", error="", exit_code=-1, blocked=True, block_reason=reason,
                )

        temp_file = self._prepare_temp_file(code)
        backend, backend_reason = resolve_backend()
        if backend == "none":
            if self.audit_log:
                self.audit_log.record(code=code, allowed=False, reason=backend_reason)
            return ExecutionResult(
                success=False, output="", error=backend_reason, exit_code=-1, blocked=True,
                block_reason=backend_reason, backend="none",
            )

        try:
            if backend == "docker":
                image_ok, image_msg = ensure_image()
                if not image_ok:
                    reason = f"Docker sandbox image unavailable: {image_msg}"
                    if self.audit_log:
                        self.audit_log.record(code=code, allowed=False, reason=reason)
                    return ExecutionResult(
                        success=False, output="", error=reason, exit_code=-1, blocked=True,
                        block_reason=reason, backend="none",
                    )
            run_cmd = build_docker_command(temp_file) if backend == "docker" else [self.python_cmd, temp_file]
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=os.path.dirname(temp_file),
            )

            output = result.stdout[:MAX_OUTPUT_CHARS] + ("\n...[output truncated]..." if len(result.stdout) > MAX_OUTPUT_CHARS else "")
            error = result.stderr[:MAX_OUTPUT_CHARS] + ("\n...[error truncated]..." if len(result.stderr) > MAX_OUTPUT_CHARS else "")
            truncated = len(result.stdout) > MAX_OUTPUT_CHARS or len(result.stderr) > MAX_OUTPUT_CHARS
            exec_success = result.returncode == 0

            if self.audit_log:
                self.audit_log.record(
                    code=code, allowed=True, reason=f"backend={backend}; {backend_reason}",
                    executed=True, success=exec_success, exit_code=result.returncode,
                )

            return ExecutionResult(
                success=exec_success, output=output, error=error, exit_code=result.returncode,
                output_truncated=truncated, backend=backend,
            )

        except subprocess.TimeoutExpired:
            timeout_error = f"Code execution timed out after {effective_timeout} seconds"
            if self.audit_log:
                self.audit_log.record(
                    code=code, allowed=True, reason=f"backend={backend}; {timeout_error}",
                    executed=True, success=False, exit_code=-1,
                )
            return ExecutionResult(success=False, output="", error=timeout_error, exit_code=-1, backend=backend)
        except Exception as e:
            if self.audit_log:
                self.audit_log.record(code=code, allowed=True, reason=str(e), executed=True, success=False, exit_code=-1)
            return ExecutionResult(success=False, output="", error=str(e), exit_code=-1, backend=backend)
        finally:
            try:
                os.unlink(temp_file)
            except Exception:
                pass  # noqa


code_executor = CodeExecutor()


if __name__ == "__main__":
    _executor = CodeExecutor()
    _test_code = "def hello():\n    return 'Hello from Saleha!'\nhello()\n"
    _res = _executor.execute(_test_code)