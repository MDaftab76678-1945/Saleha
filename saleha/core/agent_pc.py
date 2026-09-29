"""Saleha Core: Agent Personal Computer (AgentPC).

Provides every agent with a dedicated, isolated virtual workstation:
1. WorkspaceFS: Jailed filesystem environment, scratchpad memory, and time-travel checkpoints.
2. AgentSandbox: Static AST security auditor + Win32 Job Object sandbox (memory
   limit enforced on Windows only; elsewhere only the wall-clock timeout applies).
3. AgentBlackbox: SHA-256 hash-chained immutable flight recorder and verified export gate.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from saleha.core.windows_job_sandbox import SandboxRunResult, WindowsJobSandbox
from saleha.sandbox.ast_security_verifier import ASTContractAuditor

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_PC_ROOT = REPO_ROOT / ".saleha" / "agent_pcs"


@dataclass
class PCCheckpoint:
    checkpoint_id: str
    tag: str
    timestamp: float
    files: List[str]
    snapshot_path: str
    scratchpad_state: Dict[str, Any] = field(default_factory=dict)


class WorkspaceFS:
    """Jailed virtual filesystem for an agent's personal computer.

    Strictly confines all read, write, list, and delete operations inside
    the agent's root directory, preventing directory traversal attacks.
    """

    def __init__(self, root_dir: Path | str) -> None:
        self.root_path = Path(root_dir).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir = self.root_path / ".checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self._scratchpad: Dict[str, Any] = {}
        self._env_vars: Dict[str, str] = {
            "SALEHA_AGENT_WORKSPACE": str(self.root_path),
            "PYTHONIOENCODING": "utf-8",
        }

    def _resolve_safe(self, rel_path: str | Path) -> Path:
        """Resolves target path and strictly verifies it does not escape the jail."""
        target = (self.root_path / rel_path).resolve()
        try:
            target.relative_to(self.root_path)
        except ValueError as err:
            raise PermissionError(
                f"Path traversal detected: '{rel_path}' escapes agent PC root '{self.root_path}'"
            ) from err
        return target

    def write_file(self, rel_path: str | Path, content: str, overwrite: bool = True) -> Path:
        """Writes content to a file inside the agent PC workspace."""
        target = self._resolve_safe(rel_path)
        if target.exists() and not overwrite:
            raise FileExistsError(f"File '{rel_path}' already exists in agent workspace.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_file(self, rel_path: str | Path) -> str:
        """Reads content from a file inside the agent PC workspace."""
        target = self._resolve_safe(rel_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File '{rel_path}' does not exist in agent workspace.")
        return target.read_text(encoding="utf-8")

    def file_exists(self, rel_path: str | Path) -> bool:
        """Checks if a file exists inside the agent PC workspace."""
        try:
            target = self._resolve_safe(rel_path)
            return target.exists()
        except PermissionError:
            return False

    def list_files(self, subpath: str | Path = "") -> List[str]:
        """Lists all files inside the workspace or subpath, excluding system metadata."""
        if not self.root_path.exists():
            return []
        target = self._resolve_safe(subpath)
        if not target.exists() or not target.is_dir():
            return []

        rel_files: List[str] = []
        for root, dirs, files in os.walk(target):
            # Exclude internal metadata directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in sorted(files):
                if f.startswith("."):
                    continue
                p = Path(root) / f
                rel = p.relative_to(self.root_path).as_posix()
                rel_files.append(rel)
        return sorted(rel_files)

    def delete_file(self, rel_path: str | Path) -> bool:
        """Deletes a file inside the workspace."""
        target = self._resolve_safe(rel_path)
        if target.exists() and target.is_file():
            target.unlink()
            return True
        return False

    def set_scratchpad(self, key: str, value: Any) -> None:
        """Stores a temporary variable in agent PC memory."""
        self._scratchpad[key] = value

    def get_scratchpad(self, key: str, default: Any = None) -> Any:
        """Retrieves a temporary variable from agent PC memory."""
        return self._scratchpad.get(key, default)

    def get_all_scratchpad(self) -> Dict[str, Any]:
        """Returns a snapshot of the agent scratchpad memory."""
        return dict(self._scratchpad)

    def set_env(self, key: str, val: str) -> None:
        """Sets an environment variable specific to this agent PC."""
        self._env_vars[key] = val

    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Gets an environment variable specific to this agent PC."""
        return self._env_vars.get(key, default)

    def get_environ(self) -> Dict[str, str]:
        """Constructs an isolated environment mapping for processes running in this PC."""
        env = os.environ.copy()
        env.update(self._env_vars)
        return env

    def create_checkpoint(self, tag: str) -> PCCheckpoint:
        """Snapshots the entire workspace and scratchpad state."""
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.time()
        tag_clean = tag.replace(" ", "_").replace("/", "_").replace("\\", "_")
        stamp = time.time_ns()
        chk_id = f"chk_{stamp}_{tag_clean}"
        dest_dir = self.checkpoints_dir / chk_id
        while dest_dir.exists():
            stamp += 1
            chk_id = f"chk_{stamp}_{tag_clean}"
            dest_dir = self.checkpoints_dir / chk_id
        dest_dir.mkdir(parents=True)

        current_files = self.list_files()
        for f in current_files:
            src = self.root_path / f
            dst = dest_dir / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        meta = {
            "checkpoint_id": chk_id,
            "tag": tag,
            "timestamp": timestamp,
            "files": current_files,
            "scratchpad": self._scratchpad,
        }
        (dest_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        return PCCheckpoint(
            checkpoint_id=chk_id,
            tag=tag,
            timestamp=timestamp,
            files=current_files,
            snapshot_path=str(dest_dir),
            scratchpad_state=dict(self._scratchpad),
        )

    def restore_checkpoint(self, checkpoint_id_or_tag: str) -> bool:
        """Restores the workspace to a previously saved checkpoint."""
        if not self.checkpoints_dir.exists():
            return False
        target_dir: Optional[Path] = None
        if (self.checkpoints_dir / checkpoint_id_or_tag).exists():
            target_dir = self.checkpoints_dir / checkpoint_id_or_tag
        else:
            for item in sorted(self.checkpoints_dir.iterdir(), reverse=True):
                meta_file = item / "meta.json"
                if meta_file.exists():
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        if data.get("tag") == checkpoint_id_or_tag or data.get("checkpoint_id") == checkpoint_id_or_tag:
                            target_dir = item
                            break
                    except Exception:
                        continue

        if not target_dir or not target_dir.exists():
            return False

        meta_file = target_dir / "meta.json"
        if not meta_file.exists():
            return False
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

        # Clear existing non-hidden files
        for f in self.list_files():
            self.delete_file(f)

        # Restore checkpoint files
        for f in meta.get("files", []):
            src = target_dir / f
            dst = self.root_path / f
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        self._scratchpad = dict(meta.get("scratchpad", {}))
        return True

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """Lists all available checkpoints in chronological order."""
        if not self.checkpoints_dir.exists():
            return []
        checkpoints: List[Dict[str, Any]] = []
        for item in sorted(self.checkpoints_dir.iterdir()):
            meta_file = item / "meta.json"
            if meta_file.exists():
                try:
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                    checkpoints.append(data)
                except Exception:
                    continue
        return checkpoints

    def clear_workspace(self, preserve_metadata: bool = True) -> int:
        """Deletes all user files in workspace. Returns count of files deleted."""
        files = self.list_files()
        count = len(files)
        for f in files:
            self.delete_file(f)
        if not preserve_metadata:
            shutil.rmtree(self.checkpoints_dir, ignore_errors=True)
            self._scratchpad.clear()
        return count


class AgentSandbox:
    """Hardware & AST Execution Sandbox inside an agent's personal computer."""

    def __init__(
        self,
        workspace: WorkspaceFS,
        memory_limit_mb: int = 100,
        timeout_sec: float = 10.0,
    ) -> None:
        self.workspace = workspace
        self.memory_limit_mb = memory_limit_mb
        self.timeout_sec = timeout_sec
        self.job_sandbox = WindowsJobSandbox(
            memory_limit_mb=memory_limit_mb,
            timeout_ms=int(timeout_sec * 1000),
        )

    def audit_ast(self, python_code: str, require_assertions: bool = False) -> Tuple[bool, List[str]]:
        """Screens code using static ASTContractAuditor."""
        return ASTContractAuditor.audit(python_code, require_assertions=require_assertions)

    def run_python(
        self,
        code: str,
        filename: Optional[str] = None,
        verify_ast: bool = True,
        timeout_sec: Optional[float] = None,
    ) -> SandboxRunResult:
        """Executes a Python snippet or script inside the isolated workspace."""
        timeout = timeout_sec or self.timeout_sec

        # Step 1: AST Contract Audit
        if verify_ast:
            is_safe, violations = self.audit_ast(code, require_assertions=False)
            if not is_safe:
                err_msg = "[SECURITY_AUDIT_VIOLATION] " + "; ".join(violations)
                return SandboxRunResult(
                    passed=False,
                    output="",
                    error=err_msg,
                    exit_code=126,
                    execution_time_ms=0.0,
                    memory_limit_hit=False,
                    timed_out=False,
                    peak_memory_bytes=0,
                )

        # Step 2: Write temporary or named script inside workspace
        script_name = filename or f"_sandbox_run_{int(time.time() * 1000)}.py"
        script_path = self.workspace.write_file(script_name, code, overwrite=True)

        try:
            return self.job_sandbox.run_isolated(
                [sys.executable, str(script_path)],
                timeout_sec=timeout,
                cwd=str(self.workspace.root_path),
                env=self.workspace.get_environ(),
            )
        finally:
            if filename is None:
                with contextlib.suppress(Exception):
                    self.workspace.delete_file(script_name)

    def run_command(self, cmd: List[str], timeout_sec: Optional[float] = None) -> SandboxRunResult:
        """Executes a command inside the agent PC workspace under the job-object limits."""
        timeout = timeout_sec or self.timeout_sec
        return self.job_sandbox.run_isolated(
            cmd,
            timeout_sec=timeout,
            cwd=str(self.workspace.root_path),
            env=self.workspace.get_environ(),
        )


class AgentBlackbox:
    """Cryptographic Flight Recorder for an agent's personal computer.

    Maintains an append-only, SHA-256 hash-chained ledger of every decision,
    action, file mutation, and test execution.
    """

    def __init__(self, workspace: WorkspaceFS, agent_role: str) -> None:
        self.workspace = workspace
        self.agent_role = agent_role
        self.blackbox_dir = self.workspace.root_path / ".blackbox"
        self.blackbox_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.blackbox_dir / "flight_recorder.jsonl"
        self._prev_hash = self._get_last_hash()

    def _get_last_hash(self) -> str:
        """Reads the hash of the last recorded event to maintain blockchain-style chaining."""
        if not self.log_file.exists():
            return "0" * 64
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
                if lines:
                    last_event = json.loads(lines[-1])
                    return last_event.get("entry_hash", "0" * 64)
        except Exception:
            return "0" * 64
        return "0" * 64

    def record(
        self,
        event_type: str,
        stage: str,
        payload: Dict[str, Any],
        status: str = "SUCCESS",
    ) -> Dict[str, Any]:
        """Appends a hash-linked cryptographic event record to the flight log."""
        timestamp = time.time()
        payload_serialized = json.dumps(payload, sort_keys=True)
        raw_signature = f"{self._prev_hash}:{self.agent_role}:{event_type}:{stage}:{timestamp}:{payload_serialized}"
        entry_hash = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()

        event_record = {
            "timestamp": timestamp,
            "agent_role": self.agent_role,
            "event_type": event_type,
            "stage": stage,
            "status": status,
            "prev_hash": self._prev_hash,
            "entry_hash": entry_hash,
            "payload": payload,
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_record) + "\n")

        self._prev_hash = entry_hash
        return event_record

    def get_events(
        self, limit: Optional[int] = 50, event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves recent events from the blackbox; ``limit=None`` returns all."""
        if not self.log_file.exists():
            return []
        events: List[Dict[str, Any]] = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        ev = json.loads(line)
                        if event_type is None or ev.get("event_type") == event_type:
                            events.append(ev)
                    except Exception:
                        continue
        return events if limit is None else events[-limit:]

    def verify_integrity(self) -> Dict[str, Any]:
        """Mathematically verifies cryptographic hash chaining integrity."""
        if not self.log_file.exists():
            return {"status": "EMPTY", "valid": True, "total_events": 0}

        events = self.get_events(limit=None)
        expected_prev = "0" * 64

        for idx, ev in enumerate(events):
            if ev.get("prev_hash") != expected_prev:
                return {
                    "status": "COMPROMISED",
                    "valid": False,
                    "tampered_at_index": idx,
                    "event": ev,
                }

            # Recalculate hash
            payload_serialized = json.dumps(ev.get("payload", {}), sort_keys=True)
            raw = f"{ev['prev_hash']}:{ev['agent_role']}:{ev['event_type']}:{ev['stage']}:{ev['timestamp']}:{payload_serialized}"
            recomputed = hashlib.sha256(raw.encode("utf-8")).hexdigest()

            if recomputed != ev.get("entry_hash"):
                return {
                    "status": "HASH_MISMATCH",
                    "valid": False,
                    "tampered_at_index": idx,
                    "event": ev,
                }
            expected_prev = ev["entry_hash"]

        return {"status": "INTACT", "valid": True, "total_events": len(events)}

    def replay(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns chronological execution trace for time-travel debugging."""
        events = self.get_events(limit=limit or 1000)
        return [
            {
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ev["timestamp"])),
                "type": ev["event_type"],
                "stage": ev["stage"],
                "status": ev["status"],
                "summary": str(ev.get("payload", {}).get("summary", "") or ev.get("payload", {})),
            }
            for ev in events
        ]

    def has_green_run(self, filename: str, content_sha256: str) -> bool:
        """True if this exact file content has a recorded passing execution."""
        for ev in reversed(self.get_events(limit=None, event_type="SANDBOX_EXEC")):
            payload = ev.get("payload", {})
            if (
                payload.get("filename") == filename
                and payload.get("content_sha256") == content_sha256
                and ev.get("status") == "PASS"
            ):
                return True
        return False


class AgentPersonalComputer:
    """Unified Personal Computer (AgentPC) for an autonomous agent."""

    def __init__(
        self,
        agent_role: str = "agent",
        base_dir: Optional[Path | str] = None,
        memory_limit_mb: int = 100,
        timeout_sec: float = 10.0,
        *,
        agent_id: Optional[str] = None,
        workspace_root: Optional[Path | str] = None,
    ) -> None:
        role = agent_id or agent_role
        self.agent_role = role
        target_dir = workspace_root or base_dir
        if target_dir:
            self.workspace_root = Path(target_dir).resolve()
        else:
            # The role names a directory; "../.." must not put the workspace
            # (and clear_workspace) on the repo itself.
            safe_role = re.sub(r"[^\w\-]+", "_", role.lower()).strip("_") or "agent"
            self.workspace_root = DEFAULT_AGENT_PC_ROOT / safe_role

        self.workspace = WorkspaceFS(self.workspace_root)
        self.sandbox = AgentSandbox(
            self.workspace,
            memory_limit_mb=memory_limit_mb,
            timeout_sec=timeout_sec,
        )
        self.blackbox = AgentBlackbox(self.workspace, agent_role=role)

        self.blackbox.record(
            event_type="BOOT",
            stage="INIT",
            payload={"role": role, "workspace": str(self.workspace_root)},
            status="INITIALIZED",
        )

    def write_in_pc(self, filename: str, content: str) -> Path:
        """Writes a file inside the agent PC workspace."""
        return self.workspace.write_file(filename, content)

    def checkpoint_pc(self, tag: str = "checkpoint") -> str:
        """Creates a snapshot checkpoint of the agent PC workspace."""
        chk = self.workspace.create_checkpoint(tag)
        return chk.checkpoint_id

    def restore_pc(self, checkpoint_id: str) -> bool:
        """Restores the agent PC workspace to a previous checkpoint."""
        return self.workspace.restore_checkpoint(checkpoint_id)

    def execute_code(
        self,
        code: str,
        filename: str = "task.py",
        verify_ast: bool = True,
        timeout_sec: Optional[float] = None,
    ) -> SandboxRunResult:
        """Executes code in PC sandbox and logs the outcome in the flight recorder."""
        self.blackbox.record(
            event_type="CODE_EXEC_START",
            stage="SANDBOX_DISPATCH",
            payload={"filename": filename, "code_len": len(code)},
            status="PENDING",
        )

        res = self.sandbox.run_python(
            code=code,
            filename=filename,
            verify_ast=verify_ast,
            timeout_sec=timeout_sec,
        )

        status_str = "PASS" if res.passed else "FAIL"
        self.blackbox.record(
            event_type="SANDBOX_EXEC",
            stage="SANDBOX_FINISH",
            payload={
                "filename": filename,
                "content_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                "passed": res.passed,
                "exit_code": res.exit_code,
                "duration_ms": res.execution_time_ms,
                "timed_out": res.timed_out,
                "memory_limit_hit": res.memory_limit_hit,
                "error": res.error[:500] if res.error else "",
            },
            status=status_str,
        )
        return res

    def safe_mutate(
        self,
        filename: str,
        new_code: str,
        test_code: Optional[str] = None,
        verify_ast: bool = True,
    ) -> Tuple[bool, str]:
        """Surgically mutates a file in the agent PC with automatic checkpoint rollback.

        1. Creates a pre-mutation checkpoint.
        2. Writes the new code.
        3. If test_code is supplied, executes test in sandbox.
        4. If tests pass, commits mutation and records to blackbox.
        5. If tests fail, restores pre-mutation checkpoint instantly!
        """
        chk = self.workspace.create_checkpoint(f"before_mutate_{filename}")
        self.blackbox.record(
            event_type="CHECKPOINT",
            stage="SAFE_MUTATE_PRE",
            payload={"checkpoint_id": chk.checkpoint_id, "file": filename},
            status="SUCCESS",
        )

        # Write code
        self.workspace.write_file(filename, new_code)
        self.blackbox.record(
            event_type="FILE_WRITE",
            stage="MUTATION",
            payload={"filename": filename, "bytes": len(new_code)},
            status="WRITTEN",
        )

        # If no test code provided, mutation is accepted
        if not test_code:
            return True, "Code mutated successfully (no tests provided)."

        # Run test
        test_filename = f"test_{filename}"
        run_res = self.execute_code(test_code, filename=test_filename, verify_ast=verify_ast)

        if run_res.passed:
            self.blackbox.record(
                event_type="SAFE_MUTATE_COMMIT",
                stage="MUTATION_VERIFIED",
                payload={"filename": filename, "test_file": test_filename},
                status="SUCCESS",
            )
            return True, "Code mutated and verified by sandbox tests."

        # Tests failed: rollback!
        self.workspace.restore_checkpoint(chk.checkpoint_id)
        self.blackbox.record(
            event_type="SAFE_MUTATE_ROLLBACK",
            stage="MUTATION_REVERTED",
            payload={
                "filename": filename,
                "test_error": run_res.error,
                "restored_checkpoint": chk.checkpoint_id,
            },
            status="ROLLED_BACK",
        )
        return False, f"Tests failed; workspace safely rolled back. Error: {run_res.error}"

    def export_verified_artifact(
        self,
        src_relpath: str,
        dest_abspath: str | Path,
        require_green_run: bool = True,
    ) -> bool:
        """Hinton-Amodei Gate: Exports code out of the PC to an external destination.

        If require_green_run is True, exports ONLY if the blackbox holds a
        passing execution of the file's current content, byte for byte.
        """
        dest_path = Path(dest_abspath).resolve()
        if not self.workspace.file_exists(src_relpath):
            raise FileNotFoundError(f"Source file '{src_relpath}' not in agent PC.")

        content = self.workspace.read_file(src_relpath)
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if require_green_run and not self.blackbox.has_green_run(src_relpath, content_sha):
            self.blackbox.record(
                event_type="EXPORT_BLOCKED",
                stage="GATE_FAILED",
                payload={
                    "file": src_relpath,
                    "content_sha256": content_sha,
                    "reason": "No green sandbox execution of this exact content in blackbox",
                },
                status="BLOCKED",
            )
            return False

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")

        self.blackbox.record(
            event_type="EXPORT_ARTIFACT",
            stage="EXPORTED",
            payload={"src": src_relpath, "dest": str(dest_path), "bytes": len(content)},
            status="EXPORTED",
        )
        return True

    def get_pc_summary(self) -> Dict[str, Any]:
        """Provides a complete operational summary of the agent PC."""
        self.workspace.root_path.mkdir(parents=True, exist_ok=True)
        self.workspace.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        files = self.workspace.list_files()
        total_bytes = 0
        for f in files:
            with contextlib.suppress(Exception):
                p = self.workspace.root_path / f
                if p.exists():
                    total_bytes += p.stat().st_size

        events = self.blackbox.get_events(limit=5)
        checkpoints = self.workspace.list_checkpoints()
        integrity = self.blackbox.verify_integrity()

        return {
            "agent_role": self.agent_role,
            "workspace_dir": str(self.workspace.root_path),
            "files_count": len(files),
            "total_bytes": total_bytes,
            "checkpoints_count": len(checkpoints),
            "blackbox_events_count": integrity.get("total_events", 0),
            "blackbox_intact": integrity.get("valid", False),
            "recent_events": events,
            "files": files,
        }


# Global Registry for discovering active agent PCs
_AGENT_PC_REGISTRY: Dict[str, AgentPersonalComputer] = {}


def get_agent_pc(agent_role: str, base_dir: Optional[Path | str] = None) -> AgentPersonalComputer:
    """Retrieves or initializes a singleton AgentPersonalComputer for the specified agent role."""
    norm_role = agent_role.lower().strip()
    if norm_role not in _AGENT_PC_REGISTRY:
        _AGENT_PC_REGISTRY[norm_role] = AgentPersonalComputer(
            agent_role=norm_role, base_dir=base_dir
        )
    return _AGENT_PC_REGISTRY[norm_role]


def list_active_agent_pcs() -> List[Dict[str, Any]]:
    """Returns summaries for all registered Agent PCs."""
    summaries = []
    # Include both in-memory registry and any on-disk PC directories
    roles_seen: Set[str] = set(_AGENT_PC_REGISTRY.keys())
    if DEFAULT_AGENT_PC_ROOT.exists():
        for d in DEFAULT_AGENT_PC_ROOT.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                roles_seen.add(d.name)

    for r in sorted(roles_seen):
        pc = get_agent_pc(r)
        summaries.append(pc.get_pc_summary())
    return summaries


def clear_agent_pc_registry() -> None:
    """Clears cached in-memory Agent PCs (useful for test isolation)."""
    _AGENT_PC_REGISTRY.clear()


# Alias for concise developer experience
AgentPC = AgentPersonalComputer

