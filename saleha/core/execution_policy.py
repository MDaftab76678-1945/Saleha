"""
Saleha Core: Execution Backend Policy

Central configuration governing where generated code executes:

  SALEHA_SANDBOX=auto            -> Subprocess (legacy default, backward-compatible)
  SALEHA_SANDBOX=local           -> Subprocess explicitly
  SALEHA_SANDBOX=docker          -> Prefer Docker sandbox; if unavailable,
                                    degrade to subprocess with warning
  SALEHA_SANDBOX=require-docker  -> Strictly Docker; if unavailable, execution
                                    fails closed (no silent downgrade)

Docker backend isolates each execution:
  --network none            (No external network access)
  --memory / --cpus         (Resource containment)
  --pids-limit              (Fork-bomb protection)
  --security-opt no-new-privileges
Image configurable via SALEHA_DOCKER_IMAGE environment variable.

This module does not execute code directly; it serves as policy and command builder.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

VALID_MODES = ("auto", "local", "docker", "require-docker")
DEFAULT_DOCKER_IMAGE = os.getenv("SALEHA_DOCKER_IMAGE", "python:3.12-slim")

_MODE_ALIASES = {
    "strict": "require-docker",
    "required": "require-docker",
    "docker-only": "require-docker",
    "docker_required": "require-docker",
    "subprocess": "local",
    "plain": "local",
}

_probe_cache: Dict[str, object] = {"done": False, "available": False}


@dataclass
class PolicyDecision:
    backend: str             # "docker" | "subprocess" | "none"
    sandbox_mode: str        # "auto" | "local" | "docker" | "require-docker"
    docker_available: bool
    reason: str
    command: Optional[List[str]] = None


def _reset_probe_cache() -> None:
    """Reset Docker probe cache — for test isolation only."""
    _probe_cache["done"] = False
    _probe_cache["available"] = False


def get_sandbox_mode() -> str:
    """Resolves effective sandbox mode from environment (invalid value -> auto)."""
    raw = (os.getenv("SALEHA_SANDBOX") or "auto").strip().lower()
    mode = _MODE_ALIASES.get(raw, raw)
    return mode if mode in VALID_MODES else "auto"


def docker_available(force_refresh: bool = False) -> bool:
    """Determines whether Docker daemon is reachable. Result is cached per-process."""
    if _probe_cache["done"] and not force_refresh:
        return bool(_probe_cache["available"])

    available = False
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            available = (result.returncode == 0)
        except (subprocess.SubprocessError, OSError):
            available = False

    _probe_cache["done"] = True
    _probe_cache["available"] = available
    return available


def image_present(image: str) -> bool:
    """Checks whether the specified container image is locally available (`docker images -q`)."""
    if not docker_available():
        return False
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        return False


def ensure_image(image: Optional[str] = None, auto_pull: bool = True) -> Tuple[bool, str]:
    """Preflight check for sandbox image: returns OK if present, otherwise attempts pull.

    Returns:
        (ok, message) -- ok=False indicates Docker runs with this image will fail.
    """
    chosen = os.getenv("SALEHA_DOCKER_IMAGE") or image or DEFAULT_DOCKER_IMAGE
    if image_present(chosen):
        return (True, f"image '{chosen}' already present")

    if not docker_available():
        return (False, "Docker daemon unavailable")

    if os.getenv("SALEHA_DOCKER_AUTO_PULL", "1").strip() == "0" or not auto_pull:
        return (False, f"image '{chosen}' not present and auto-pull disabled")

    try:
        result = subprocess.run(
            ["docker", "pull", chosen],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return (True, f"pulled image '{chosen}'")
        return (False, f"docker pull failed: {(result.stderr or result.stdout).strip()[:200]}")
    except (subprocess.SubprocessError, OSError) as err:
        return (False, f"docker pull error: {err}")


def build_docker_command(
    host_script_path: str,
    image: str = DEFAULT_DOCKER_IMAGE,
    memory: str = "512m",
    cpus: str = "1.0",
    pids_limit: int = 128,
    custom_args: Optional[List[str]] = None,
) -> List[str]:
    """Constructs hardened `docker run` command for a host script.

    Mounts script parent directory read-write to /sandbox, while blocking network,
    capping resources, and preventing privilege escalation.
    """
    chosen_image = os.getenv("SALEHA_DOCKER_IMAGE") or image
    normalized = host_script_path.replace("\\", "/")
    host_dir = os.path.dirname(os.path.abspath(normalized)).replace("\\", "/") or "."
    script_name = normalized.rsplit("/", 1)[-1]

    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", memory,
        "--cpus", cpus,
        "--pids-limit", str(pids_limit),
        "--security-opt", "no-new-privileges",
        "-v", f"{host_dir}:/sandbox",
        "-w", "/sandbox",
        chosen_image,
        "python", f"/sandbox/{script_name}",
    ]
    if custom_args:
        cmd.extend(custom_args)
    return cmd


class ExecutionPolicy:
    """Manages execution backend selection, security policies, and command construction."""

    def __init__(
        self,
        mode: Optional[str] = None,
        docker_image: Optional[str] = None,
        memory: str = "512m",
        cpus: str = "1.0",
        pids_limit: int = 128,
    ) -> None:
        self._override_mode = mode
        self.docker_image = docker_image or os.getenv("SALEHA_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE)
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit

    def get_mode(self) -> str:
        if self._override_mode:
            clean = _MODE_ALIASES.get(self._override_mode.strip().lower(), self._override_mode.strip().lower())
            return clean if clean in VALID_MODES else "auto"
        return get_sandbox_mode()

    def is_docker_available(self, force_refresh: bool = False) -> bool:
        return docker_available(force_refresh=force_refresh)

    def resolve_backend(self) -> Tuple[str, str]:
        """Resolves effective execution backend based on policy and environment."""
        mode = self.get_mode()

        if mode in ("auto", "local"):
            return ("subprocess", f"sandbox mode '{mode}' uses local subprocess")

        daemon_up = self.is_docker_available()

        if mode == "docker":
            if daemon_up:
                return ("docker", "sandbox mode 'docker': containerized execution")
            return (
                "subprocess",
                "sandbox mode 'docker' but Docker unavailable -- degraded to "
                "subprocess. Set SALEHA_SANDBOX=require-docker to forbid this.",
            )

        # require-docker
        if daemon_up:
            return ("docker", "sandbox mode 'require-docker': containerized execution enforced")
        return (
            "none",
            "SALEHA_SANDBOX=require-docker is set but the Docker daemon is "
            "unavailable. Execution refused (fail-closed) instead of silently "
            "running with full host privileges.",
        )

    def build_command(
        self,
        host_script_path: str,
        custom_args: Optional[List[str]] = None,
    ) -> List[str]:
        backend, _ = self.resolve_backend()
        if backend == "docker":
            return build_docker_command(
                host_script_path=host_script_path,
                image=self.docker_image,
                memory=self.memory,
                cpus=self.cpus,
                pids_limit=self.pids_limit,
                custom_args=custom_args,
            )
        cmd = ["python", host_script_path]
        if custom_args:
            cmd.extend(custom_args)
        return cmd

    def evaluate_policy(self, host_script_path: Optional[str] = None) -> PolicyDecision:
        backend, reason = self.resolve_backend()
        daemon_up = self.is_docker_available()
        mode = self.get_mode()
        cmd = self.build_command(host_script_path) if host_script_path and backend != "none" else None
        return PolicyDecision(
            backend=backend,
            sandbox_mode=mode,
            docker_available=daemon_up,
            reason=reason,
            command=cmd,
        )


execution_policy = ExecutionPolicy()


def resolve_backend() -> Tuple[str, str]:
    """Resolves effective execution backend based on environment policy."""
    return execution_policy.resolve_backend()

