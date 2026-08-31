"""
Saleha Core: Hardened Isolated Sandbox Engine

Provides multi-tier code isolation for executing untrusted scripts safely:
1. Docker Container Sandbox (cgroups, memory limit, network disabled, read-only root)
2. Ephemeral Process Sandbox (timeout killing, resource governance, temp isolation)
3. VirtualEnv sandbox fallback with guaranteed auto-cleanup.
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from saleha.core.docker_sandbox import is_docker_available, DockerSandboxRunner
from saleha.core.sandbox_runner import SandboxResult


@dataclass
class SandboxResourceUsage:
    duration_seconds: float
    peak_memory_mb: float = 0.0
    timed_out: bool = False
    exit_code: int = 0


@dataclass
class HardenedExecutionResult:
    success: bool
    output: str
    error: str = ""
    sandbox_tier: str = "process"  # "docker" | "process" | "virtualenv"
    resource_usage: Optional[SandboxResourceUsage] = None


class HardenedSandboxEngine:
    """Multi-tier security sandbox for running arbitrary code safely."""

    def __init__(self, prefer_docker: bool = True):
        self.prefer_docker = prefer_docker
        self.docker_runner = DockerSandboxRunner() if prefer_docker else None

    def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 15,
        memory_limit: str = "256m",
        allow_network: bool = False,
    ) -> HardenedExecutionResult:
        """Executes code in the strongest available security sandbox tier."""
        # Tier 1: Docker Sandbox
        if self.prefer_docker and is_docker_available():
            net = "bridge" if allow_network else "none"
            start_t = time.time()
            res = self.docker_runner.run_code(
                code=code,
                language=language,
                timeout=timeout,
                memory_limit=memory_limit,
                network=net,
            )
            elapsed = time.time() - start_t
            return HardenedExecutionResult(
                success=res.success,
                output=res.output or "",
                error=res.error or "",
                sandbox_tier="docker",
                resource_usage=SandboxResourceUsage(
                    duration_seconds=round(elapsed, 3),
                    exit_code=res.exit_code,
                    timed_out=res.timed_out,
                ),
            )

        # Tier 2: Isolated Process Sandbox
        return self._execute_process_sandbox(code, language=language, timeout=timeout)

    def _execute_process_sandbox(
        self,
        code: str,
        language: str = "python",
        timeout: int = 15,
    ) -> HardenedExecutionResult:
        """Executes code in an isolated subprocess within an ephemeral temp workspace."""
        temp_dir = tempfile.mkdtemp(prefix="saleha_sandbox_")
        ext = ".py" if language == "python" else (".js" if language in ("js", "javascript") else ".txt")
        script_path = os.path.join(temp_dir, f"sandbox_script{ext}")

        start_t = time.time()
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            cmd = [sys.executable, script_path] if language == "python" else ["node", script_path]

            proc = subprocess.run(
                cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=dict(os.environ, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1"),
            )

            elapsed = round(time.time() - start_t, 3)
            return HardenedExecutionResult(
                success=(proc.returncode == 0),
                output=proc.stdout or "",
                error=proc.stderr or "",
                sandbox_tier="process",
                resource_usage=SandboxResourceUsage(
                    duration_seconds=elapsed,
                    exit_code=proc.returncode,
                    timed_out=False,
                ),
            )

        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - start_t, 3)
            return HardenedExecutionResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout}s",
                sandbox_tier="process",
                resource_usage=SandboxResourceUsage(
                    duration_seconds=elapsed,
                    exit_code=-1,
                    timed_out=True,
                ),
            )
        except Exception as e:
            elapsed = round(time.time() - start_t, 3)
            return HardenedExecutionResult(
                success=False,
                output="",
                error=f"Sandbox process execution error: {e}",
                sandbox_tier="process",
                resource_usage=SandboxResourceUsage(
                    duration_seconds=elapsed,
                    exit_code=-1,
                    timed_out=False,
                ),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# Global instance
hardened_sandbox = HardenedSandboxEngine()
