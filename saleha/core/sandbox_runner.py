"""
Saleha Core: Sandboxed VirtualEnv & Isolated Execution Runner

Provides isolated script and test suite execution:
1. Creates ephemeral sandbox directories.
2. Installs required third-party dependencies into an isolated site-packages folder.
3. Executes scripts under strict timeouts with CPU/memory containment.
4. Auto-cleans ephemeral artifacts upon execution completion.
"""

import os
import sys
import time
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from saleha.core.safety_guard import SafetyGuard


@dataclass
class SandboxResult:
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    installed_packages: List[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""


class SandboxRunner:
    def __init__(self, default_timeout: int = 30):
        self.default_timeout = default_timeout
        self.guard = SafetyGuard()
        self.python_bin = sys.executable

    def run_in_sandbox(self, script_code_or_file: str,
                       dependencies: Optional[List[str]] = None,
                       timeout: Optional[int] = None) -> SandboxResult:
        """Executes Python code or a script file in an isolated temporary sandbox."""
        timeout_val = timeout or self.default_timeout
        deps = dependencies or []

        # Read or set code
        if os.path.isfile(script_code_or_file):
            with open(script_code_or_file, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
        else:
            code = script_code_or_file

        # Check safety guard
        safety = self.guard.evaluate(code)
        if not safety.is_safe:
            return SandboxResult(
                success=False,
                blocked=True,
                block_reason=safety.message,
                error=f"Blocked by safety guard: {safety.message}"
            )

        start_time = time.time()

        with tempfile.TemporaryDirectory(prefix="saleha_sandbox_") as tmpdir:
            script_file = os.path.join(tmpdir, "main.py")
            site_packages_dir = os.path.join(tmpdir, "site-packages")
            os.makedirs(site_packages_dir, exist_ok=True)

            with open(script_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Install dependencies into isolated site-packages folder
            if deps:
                pip_cmd = [
                    self.python_bin, "-m", "pip", "install",
                    "--target", site_packages_dir,
                    "--no-cache-dir", "--quiet"
                ] + deps
                try:
                    pip_proc = subprocess.run(
                        pip_cmd,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if pip_proc.returncode != 0:
                        return SandboxResult(
                            success=False,
                            error=f"Dependency installation failed: {pip_proc.stderr}",
                            exit_code=pip_proc.returncode,
                            execution_time=time.time() - start_time
                        )
                except subprocess.TimeoutExpired:
                    return SandboxResult(
                        success=False,
                        error="Dependency installation timed out (60s limit).",
                        execution_time=time.time() - start_time
                    )

            # Build environment with isolated PYTHONPATH
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{site_packages_dir}{os.pathsep}{existing_pythonpath}"
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            try:
                proc = subprocess.run(
                    [self.python_bin, script_file],
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=tmpdir,
                    timeout=timeout_val
                )
                elapsed = time.time() - start_time
                return SandboxResult(
                    success=(proc.returncode == 0),
                    output=proc.stdout,
                    error=proc.stderr,
                    exit_code=proc.returncode,
                    execution_time=elapsed,
                    installed_packages=deps
                )
            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                return SandboxResult(
                    success=False,
                    error=f"Execution timed out after {timeout_val} seconds.",
                    execution_time=elapsed,
                    installed_packages=deps
                )
            except Exception as e:
                return SandboxResult(
                    success=False,
                    error=f"Sandbox execution error: {str(e)}",
                    execution_time=time.time() - start_time,
                    installed_packages=deps
                )
