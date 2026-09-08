"""
Saleha Core: Codebase Snapshot & Time-Machine Rollback (TimeMachine)

Provides atomic workspace snapshots and 1-click rollback:
1. Capture the state of files before complex multi-file agent refactoring.
2. Persist each snapshot to disk (.saleha/snapshots/) so a snapshot taken in
   one process can be rolled back from another.
3. Rollback if automated tests fail or the workspace is corrupted.
"""

import os
import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class CodebaseSnapshot:
    """Represents an atomic point-in-time snapshot of files."""
    snapshot_id: str
    label: str
    files: Dict[str, str]  # filepath -> content
    file_count: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the snapshot for disk storage."""
        return {
            "snapshot_id": self.snapshot_id,
            "label": self.label,
            "files": self.files,
            "file_count": self.file_count,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodebaseSnapshot":
        """Rebuilds a snapshot from its on-disk form."""
        return cls(
            snapshot_id=data["snapshot_id"],
            label=data["label"],
            files=data["files"],
            file_count=data["file_count"],
            timestamp=data.get("timestamp", 0.0),
        )


class TimeMachine:
    """Disk-backed workspace snapshot and rollback manager."""

    def __init__(self, max_snapshots: int = 20, store_dir: Optional[str] = None):
        """Initializes the time machine engine.

        store_dir defaults to .saleha/snapshots/ under the current working
        directory. Passing an explicit path is mainly for tests.
        """
        self.max_snapshots = max_snapshots
        self.store_dir = store_dir or os.path.join(os.getcwd(), ".saleha", "snapshots")

    def _snapshot_path(self, snapshot_id: str) -> str:
        """Returns the on-disk JSON path for a snapshot id."""
        return os.path.join(self.store_dir, f"{snapshot_id}.json")

    def _load_all(self) -> List[CodebaseSnapshot]:
        """Reads every snapshot on disk, ordered oldest to newest."""
        if not os.path.isdir(self.store_dir):
            return []
        loaded: List[CodebaseSnapshot] = []
        for name in os.listdir(self.store_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.store_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded.append(CodebaseSnapshot.from_dict(json.load(f)))
            except (OSError, ValueError, KeyError):
                # A corrupt or partial file is skipped rather than crashing the
                # whole listing; rollback to a bad snapshot is not offered.
                continue
        loaded.sort(key=lambda s: s.timestamp)
        return loaded

    def _prune(self) -> None:
        """Deletes the oldest snapshot files past max_snapshots."""
        existing = self._load_all()
        excess = len(existing) - self.max_snapshots
        for snap in existing[:max(0, excess)]:
            try:
                os.remove(self._snapshot_path(snap.snapshot_id))
            except OSError:
                pass

    def create_snapshot(self, target_paths: List[str], label: str = "auto_snapshot") -> CodebaseSnapshot:
        """Captures the current state of the given files and writes it to disk."""
        captured_files: Dict[str, str] = {}
        for path in target_paths:
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        captured_files[os.path.abspath(path)] = f.read()
                except OSError:
                    pass

        snap_id = f"snap_{int(time.time() * 1000)}"
        snapshot = CodebaseSnapshot(
            snapshot_id=snap_id,
            label=label,
            files=captured_files,
            file_count=len(captured_files),
        )

        os.makedirs(self.store_dir, exist_ok=True)
        with open(self._snapshot_path(snap_id), "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        self._prune()
        return snapshot

    def rollback(self, snapshot_id: Optional[str] = None) -> tuple[bool, str]:
        """Restores workspace files to the specified snapshot (or the latest)."""
        snapshots = self._load_all()
        if not snapshots:
            return False, "No snapshots available to rollback."

        target_snap: Optional[CodebaseSnapshot] = None
        if snapshot_id:
            for s in reversed(snapshots):
                if s.snapshot_id == snapshot_id:
                    target_snap = s
                    break
        else:
            target_snap = snapshots[-1]

        if not target_snap:
            return False, f"Snapshot '{snapshot_id}' not found."

        restored_count = 0
        for path, content in target_snap.files.items():
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                restored_count += 1
            except OSError:
                pass

        return True, f"Successfully rolled back {restored_count} file(s) to snapshot '{target_snap.snapshot_id}' ({target_snap.label})."

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Lists metadata of all snapshots currently on disk."""
        return [
            {
                "snapshot_id": s.snapshot_id,
                "label": s.label,
                "file_count": s.file_count,
                "timestamp": s.timestamp,
            }
            for s in self._load_all()
        ]


time_machine = TimeMachine()


if __name__ == "__main__":
    _tm = TimeMachine()
    _s = _tm.create_snapshot(["pyproject.toml"], label="before_test")
    print(f"created {_s.snapshot_id}, {_s.file_count} file(s); "
          f"{len(_tm.list_snapshots())} snapshot(s) on disk")
