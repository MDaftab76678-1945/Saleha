"""
POSIX process jail with hard resource ceilings.

## Why this file is guarded

`NOTEBOOK_IMPORT.md` imported this directory and described it as the
"**Real sandbox** -- `saleha/core/` only has sandbox theater". On the machine
that note was written on, the module could not be imported at all:

    >>> import saleha.sandbox.sandbox_jail
    ModuleNotFoundError: No module named 'resource'

`resource` is POSIX-only and `preexec_fn` is not supported on Windows, so the
whole mechanism -- rlimits applied between fork and exec -- has no Windows
equivalent. The import was unguarded, so the failure came out as a confusing
`ModuleNotFoundError` about a stdlib module rather than "this needs Linux or
macOS".

The jail itself is real and unchanged. What is new is that the module imports
everywhere and says plainly where it can run, so a caller can check
`HardenedSandbox.is_available()` instead of discovering the platform limit
through a traceback. On Windows, use `saleha.core.windows_job_sandbox`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Any, Dict

try:
    # POSIX only. Typed as Any so a type checker running on Windows -- where
    # the stub has no RLIMIT_* members -- does not report a dozen errors for
    # code that is guarded by is_available() and only ever runs on POSIX.
    import resource as _resource

    resource: Any = _resource
except ImportError:  # pragma: no cover - platform dependent
    resource = None


class SandboxUnavailableError(RuntimeError):
    """Raised when the jail is used on a platform that cannot enforce it."""


class HardenedSandbox:
    """POSIX isolated worker process with strict memory, CPU, and process count ceilings."""

    def __init__(self, max_mem_mb: int = 128, max_cpu_sec: int = 3, max_procs: int = 4):
        self.max_mem_bytes = max_mem_mb * 1024 * 1024
        self.max_cpu_sec = max_cpu_sec
        self.max_procs = max_procs

    @staticmethod
    def is_available() -> bool:
        """
        True only where the limits can actually be enforced.

        This is not a style check. Without `resource` and `preexec_fn` the
        memory cap, CPU cap and fork-bomb guard are all absent, and a sandbox
        that silently enforces none of its limits is worse than no sandbox --
        the caller believes the code is contained.
        """
        return resource is not None and hasattr(os, "fork")

    @staticmethod
    def unavailable_reason() -> str:
        if resource is not None and hasattr(os, "fork"):
            return ""
        return (
            f"the POSIX process jail needs the `resource` module and fork "
            f"(this is {sys.platform}). rlimits cannot be applied here, so "
            f"the memory, CPU and process ceilings would not be enforced. "
            f"Use saleha.core.windows_job_sandbox on Windows."
        )

    def _set_security_rlimits(self):  # pragma: no cover - runs post-fork
        assert resource is not None  # guarded by is_available()
        # 1. Virtual memory limit
        resource.setrlimit(resource.RLIMIT_AS, (self.max_mem_bytes, self.max_mem_bytes))
        # 2. CPU execution time limit
        resource.setrlimit(resource.RLIMIT_CPU, (self.max_cpu_sec, self.max_cpu_sec))
        # 3. Prevent fork bombs (Process limit)
        resource.setrlimit(resource.RLIMIT_NPROC, (self.max_procs, self.max_procs))
        # 4. Disable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # 5. Limit file creation size (1MB max output)
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        # 6. Limit open file descriptors
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))

    def run_isolated(self, python_code: str) -> Dict[str, Any]:
        """
        Run `python_code` in a jailed subprocess.

        Refuses outright where the limits cannot be enforced, rather than
        running the code unconfined and reporting it as sandboxed.
        """
        if not self.is_available():
            raise SandboxUnavailableError(self.unavailable_reason())

        with tempfile.TemporaryDirectory() as jail_dir:
            file_path = os.path.join(jail_dir, "jailed_workload.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(python_code)

            clean_env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONUNBUFFERED": "1",
                "LANG": "C.UTF-8"
            }

            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.max_cpu_sec + 1,
                    preexec_fn=self._set_security_rlimits,
                    cwd=jail_dir,
                    env=clean_env
                )
                return {
                    "passed": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip()
                }
            except subprocess.TimeoutExpired:
                return {"passed": False, "exit_code": -1, "stdout": "", "stderr": "SIGKILL: Execution timed out."}
            except Exception as ex:
                return {"passed": False, "exit_code": -2, "stdout": "", "stderr": f"Sandbox Exception: {ex}"}
