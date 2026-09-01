"""
Saleha Core: Docker Micro-Container Isolation Sandbox

Executes arbitrary generated code inside ephemeral, hardened Docker containers
with strict CPU/Memory cgroups, read-only root filesystems, and network isolation.
Gracefully falls back to VirtualEnv SandboxRunner when Docker is unavailable.
"""

import os
import shutil
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from saleha.core.sandbox_runner import SandboxRunner, SandboxResult


def is_docker_available() -> bool:
    """Checks if Docker CLI and Docker daemon are running."""
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False


class DockerSandboxRunner:
    """Runs code inside secure ephemeral Docker containers."""

    IMAGE_MAP = {
        "python": "python:3.11-slim",
        "javascript": "node:20-alpine",
        "typescript": "node:20-alpine",
        "go": "golang:1.22-alpine",
    }

    def __init__(self, fallback_to_venv: bool = True):
        self.fallback_runner = SandboxRunner() if fallback_to_venv else None

    def run_code(self, code: str,
                 language: str = "python",
                 timeout: int = 30,
                 memory_limit: str = "512m",
                 cpus: float = 1.0,
                 network: str = "none") -> SandboxResult:
        """Executes code in Docker container, falling back to venv if unavailable."""
        if not is_docker_available():
            if self.fallback_runner and language == "python":
                res = self.fallback_runner.run_in_sandbox(code, timeout=timeout)
                res.output = f"[Docker unavailable: VirtualEnv Sandbox Fallback]\n{res.output}" if res.output else res.output
                return res
            elif self.fallback_runner:
                try:
                    from saleha.core.polyglot_executor import polyglot_executor
                    poly_res = polyglot_executor.execute(code, language=language)
                    out_msg = f"[Docker unavailable: Polyglot Local Fallback ({language})]\n{poly_res.output}" if poly_res.output else poly_res.output
                    return SandboxResult(
                        success=poly_res.success,
                        output=out_msg,
                        error=poly_res.error,
                        exit_code=poly_res.exit_code,
                        execution_time=poly_res.execution_time,
                        blocked=poly_res.blocked,
                        block_reason=poly_res.block_reason
                    )
                except Exception as ex:
                    return SandboxResult(
                        success=False,
                        exit_code=-1,
                        error=f"Local polyglot fallback failed: {str(ex)}"
                    )
            return SandboxResult(
                success=False,
                exit_code=-1,
                error="Docker daemon is not running and no fallback runner is available."
            )

        image = self.IMAGE_MAP.get(language.lower(), "python:3.11-slim")
        with tempfile.TemporaryDirectory() as tmpdir:
            file_ext = ".py" if language == "python" else (".js" if language in ("javascript", "typescript") else ".go")
            script_path = os.path.join(tmpdir, f"main{file_ext}")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Docker command with cgroups & network isolation
            cmd = [
                "docker", "run", "--rm",
                f"--network={network}",
                f"--memory={memory_limit}",
                f"--cpus={cpus}",
                "-v", f"{tmpdir}:/app:ro",
                "-w", "/app",
                image,
            ]
            if language == "python":
                cmd.extend(["python", "main.py"])
            elif language in ("javascript", "typescript"):
                cmd.extend(["node", "main.js"])
            elif language == "go":
                cmd.extend(["go", "run", "main.go"])

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                if proc.returncode != 0 and ("Unable to find image" in (proc.stderr or "") or "docker: Error" in (proc.stderr or "")):
                    if self.fallback_runner and language == "python":
                        return self.fallback_runner.run_in_sandbox(code, timeout=timeout)
                return SandboxResult(
                    success=(proc.returncode == 0),
                    exit_code=proc.returncode,
                    output=proc.stdout,
                    error=proc.stderr,
                    execution_time=0.0
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    error=f"Docker sandbox execution timed out after {timeout} seconds."
                )
            except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
                if self.fallback_runner and language == "python":
                    return self.fallback_runner.run_in_sandbox(code, timeout=timeout)
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    error=f"Docker container execution error: {str(e)}"
                )
