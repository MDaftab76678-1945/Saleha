"""
Saleha Core: bridge to the Rust Intent Kernel (`ik`, rust/intent-kernel).

The kernel keeps a SHA-256 hash-chained proof ledger. Saleha uses it as an
*external anchor* for its own WorkLedger: every work-ledger entry's hash is
also appended to a kernel ledger kept outside the repo. A holder of the
repo's ledger file can delete an entry and recompute that chain, and nothing
inside the file will look wrong (work_ledger.py documents the attack); the
kernel ledger still lists the removed entry, so the mismatch shows.

Every call reports whether the kernel actually ran. A missing binary is
`available=False` with the build command, never a silent pass.

Build once:  cargo build --release -p ik   (from rust/)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_HINT = "cd rust && cargo build --release -p ik"


def default_anchor_path() -> str:
    """Where Saleha keeps its external anchor: outside any repo it works on.

    SALEHA_ANCHOR_LEDGER overrides it.
    """
    return os.environ.get("SALEHA_ANCHOR_LEDGER") or str(Path.home() / ".saleha" / "anchors.jsonl")


def find_ik() -> Optional[str]:
    """Path of the ik binary: SALEHA_IK, then rust/target/{release,debug}, then PATH."""
    override = os.environ.get("SALEHA_IK")
    if override:
        return override if Path(override).is_file() else None
    exe = "ik.exe" if os.name == "nt" else "ik"
    for build in ("release", "debug"):
        candidate = _REPO_ROOT / "rust" / "target" / build / exe
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ik")


def _run(args: List[str], stdin: str = "", timeout: float = 30.0) -> Dict[str, Any]:
    ik = find_ik()
    if ik is None:
        return {"available": False, "detail": f"intent kernel not built ({BUILD_HINT})"}
    try:
        proc = subprocess.run([ik, *args], input=stdin, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "detail": f"could not run {ik}: {exc}"}
    return {"available": True, "returncode": proc.returncode,
            "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def append_event(proof_path: str, mission: str, event: str,
                 input_data: Any, output_data: Any) -> Dict[str, Any]:
    """Append one event through the kernel. Returns {"ok", "hash"|"detail", ...}."""
    res = _run(["proof-append", "--proof", proof_path, "--mission", mission,
                "--event", event],
               stdin=json.dumps({"input": input_data, "output": output_data}))
    if not res["available"]:
        return {"ok": False, "available": False, "detail": res["detail"]}
    if res["returncode"] != 0:
        # The kernel refuses to append to a ledger whose chain is broken.
        return {"ok": False, "available": True,
                "detail": (res["stderr"] or res["stdout"])[-300:]}
    try:
        out = json.loads(res["stdout"].splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "available": True,
                "detail": f"unexpected kernel output: {res['stdout'][-200:]}"}
    return {"ok": True, "available": True, **out}


def verify_ledger(proof_path: str) -> Dict[str, Any]:
    """Kernel-side chain check. {"available", "valid", "events", "detail"}."""
    res = _run(["verify-proof", "--proof", proof_path, "--json"])
    if not res["available"]:
        return {"available": False, "valid": False, "events": 0, "detail": res["detail"]}
    try:
        out = json.loads(res["stdout"].splitlines()[-1])
    except (ValueError, IndexError):
        return {"available": True, "valid": False, "events": 0,
                "detail": f"kernel could not read the ledger: {(res['stderr'] or res['stdout'])[-200:]}"}
    return {"available": True, "valid": bool(out.get("valid")) and res["returncode"] == 0,
            "events": int(out.get("events", 0)), "detail": ""}


def read_events(proof_path: str) -> List[Dict[str, Any]]:
    """Raw kernel ledger events. Integrity is the kernel's job (verify_ledger)."""
    path = Path(proof_path)
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except ValueError:
                events.append({"corrupt": line[:200]})
    return events


def is_available() -> bool:
    """Return True if the Rust intent kernel binary is found and runnable."""
    return find_ik() is not None


def run_mission(goal: str, dry_run: bool = False, proof_path: Optional[str] = None, timeout: float = 120.0) -> Dict[str, Any]:
    """Execute an autonomous goal via Rust intent-kernel plan compiler and executor."""
    args = ["run", "--goal", goal]
    if dry_run:
        args.append("--dry-run")
    if proof_path:
        args.extend(["--proof", proof_path])
    return _run(args, timeout=timeout)


def solve_task(task: str, language: str = "python", model: str = "qwen2.5-coder:3b", max_attempts: int = 5, timeout: float = 180.0) -> Dict[str, Any]:
    """Intelligent problem solving with Reflexion loop in Rust intent-kernel."""
    args = ["solve", "--task", task, "--language", language, "--model", model, "--max-attempts", str(max_attempts)]
    return _run(args, timeout=timeout)


def autocode_task(task: str, language: str = "python", model: str = "qwen2.5-coder:3b", timeout: float = 180.0) -> Dict[str, Any]:
    """Run multi-agent negotiation with auto-verification in Rust intent-kernel."""
    args = ["autocode", "--task", task, "--language", language, "--model", model]
    return _run(args, timeout=timeout)


def generate_code(task: str, language: str = "python", model: str = "qwen2.5-coder:3b", output: Optional[str] = None, timeout: float = 120.0) -> Dict[str, Any]:
    """Generate verified code using LLM via Rust intent-kernel."""
    args = ["generate", "--task", task, "--language", language, "--model", model]
    if output:
        args.extend(["--output", output])
    return _run(args, timeout=timeout)


def get_status() -> Dict[str, Any]:
    """Return status summary from Rust intent-kernel."""
    return _run(["status"], timeout=10.0)


def get_architecture() -> Dict[str, Any]:
    """Return architecture map from Rust intent-kernel."""
    return _run(["architecture"], timeout=10.0)

