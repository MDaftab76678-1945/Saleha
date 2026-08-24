"""
Saleha Core: Execution Backend Policy

Ek jagah decide hota hai ki generated code KAHAN chalega:

  SALEHA_SANDBOX=auto            -> subprocess (legacy default, backward-compatible)
  SALEHA_SANDBOX=local           -> subprocess explicitly
  SALEHA_SANDBOX=docker          -> Docker sandbox prefer karo; unavailable ho
                                    to subprocess pe degrade (warning ke saath)
  SALEHA_SANDBOX=require-docker  -> SIRF Docker; unavailable ho to execution
                                    fail-closed hogi (koi silent downgrade nahi)

Docker backend har run ko isolate karta hai:
  --network none            (no network access)
  --memory / --cpus         (resource containment)
  --pids-limit              (fork-bomb guard)
  --security-opt no-new-privileges
Image SALEHA_DOCKER_IMAGE env se override ho sakta hai.

Ye module khud koi code execute nahi karta -- sirf policy + command builder.
"""

import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

VALID_MODES = ("auto", "local", "docker", "require-docker")
DEFAULT_DOCKER_IMAGE = "python:3.12-slim"

_MODE_ALIASES = {
    "strict": "require-docker",
    "required": "require-docker",
    "docker-only": "require-docker",
    "docker_required": "require-docker",
    "subprocess": "local",
    "plain": "local",
}

_probe_cache: Dict[str, object] = {"done": False, "available": False}


def get_sandbox_mode() -> str:
    """Env se effective sandbox mode resolve karta hai (invalid value -> auto)."""
    raw = (os.getenv("SALEHA_SANDBOX") or "auto").strip().lower()
    mode = _MODE_ALIASES.get(raw, raw)
    return mode if mode in VALID_MODES else "auto"


def docker_available(force_refresh: bool = False) -> bool:
    """Docker daemon reachable hai? Result process-lifetime cache hota hai."""
    if _probe_cache["done"] and not force_refresh:
        return bool(_probe_cache["available"])  # type: ignore[arg-type]

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
    """Kya ye image locally available hai? (`docker images -q`)"""
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
    """Sandbox image preflight: present hai to OK, warna ek hi baar
    `docker pull` karta hai (SALEHA_DOCKER_AUTO_PULL=0 se disable).

    Returns:
        (ok, message) -- ok=False ka matlab Docker run is image se fail hoga.
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


def resolve_backend() -> Tuple[str, str]:
    """Effective backend decide karta hai.

    Returns:
        ("docker"|"subprocess"|"none", human-readable reason)
        "none" ka matlab: require-docker mode me Docker nahi mila ->
        caller ko fail-closed response dena chahiye.
    """
    mode = get_sandbox_mode()

    if mode in ("auto", "local"):
        return ("subprocess", f"sandbox mode '{mode}' uses local subprocess")

    daemon_up = docker_available()

    if mode == "docker":
        if daemon_up:
            return ("docker", "sandbox mode 'docker': containerized execution")
        return (
            "subprocess",
            "sandbox mode 'docker' but Docker unavailable -- degraded to "
            "subprocess. Set SALEHA_SANDBOX=require-docker to forbid this."
        )

    # require-docker
    if daemon_up:
        return ("docker", "sandbox mode 'require-docker': containerized execution enforced")
    return (
        "none",
        "SALEHA_SANDBOX=require-docker is set but the Docker daemon is "
        "unavailable. Execution refused (fail-closed) instead of silently "
        "running with full host privileges."
    )


def build_docker_command(
    host_script_path: str,
    image: str = DEFAULT_DOCKER_IMAGE,
    memory: str = "512m",
    cpus: str = "1.0",
) -> List[str]:
    """Host temp-script ke liye hardened `docker run` command banata hai.

    Script apne parent directory ke saath read-write /sandbox par mount hota
    hai taaki script khud sibling files likh sake (tests waghera), lekin
    network band, resources capped, aur privilege-escalation blocked rehta hai.
    """
    chosen_image = os.getenv("SALEHA_DOCKER_IMAGE") or image
    host_dir = os.path.dirname(os.path.abspath(host_script_path))
    script_name = os.path.basename(host_script_path)

    return [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", memory,
        "--cpus", cpus,
        "--pids-limit", "128",
        "--security-opt", "no-new-privileges",
        "-v", f"{host_dir}:/sandbox",
        "-w", "/sandbox",
        chosen_image,
        "python", f"/sandbox/{script_name}",
    ]
