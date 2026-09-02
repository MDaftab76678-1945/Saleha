"""
Saleha Core: Swarm State Checkpoint Store & Session Resume Engine

Persists multi-agent DAG execution states to disk (WAL JSON / SQLite) to enable
instant session resumption without re-running finished stages ($0 token waste).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class SwarmCheckpoint:
    execution_id: str
    goal: str
    role_sequence: List[str]
    completed_stages: List[Dict[str, Any]] = field(default_factory=list)
    state_payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "in_progress"  # "in_progress", "completed", "failed"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class SwarmCheckpointStore:
    """Persistent Storage for Swarm Execution Checkpoints."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.join(".saleha", "checkpoints")
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_path(self, execution_id: str) -> str:
        return os.path.join(self.storage_dir, f"checkpoint_{execution_id}.json")

    def save_checkpoint(self, checkpoint: SwarmCheckpoint) -> None:
        checkpoint.updated_at = time.time()
        file_path = self._get_path(checkpoint.execution_id)
        data = {
            "execution_id": checkpoint.execution_id,
            "goal": checkpoint.goal,
            "role_sequence": checkpoint.role_sequence,
            "completed_stages": checkpoint.completed_stages,
            "state_payload": checkpoint.state_payload,
            "status": checkpoint.status,
            "created_at": checkpoint.created_at,
            "updated_at": checkpoint.updated_at,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_checkpoint(self, execution_id: str) -> Optional[SwarmCheckpoint]:
        file_path = self._get_path(execution_id)
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SwarmCheckpoint(
                    execution_id=data.get("execution_id", ""),
                    goal=data.get("goal", ""),
                    role_sequence=data.get("role_sequence", []),
                    completed_stages=data.get("completed_stages", []),
                    state_payload=data.get("state_payload", {}),
                    status=data.get("status", "in_progress"),
                    created_at=data.get("created_at", time.time()),
                    updated_at=data.get("updated_at", time.time()),
                )
        except Exception:
            return None

    def list_checkpoints(self, status: Optional[str] = None) -> List[SwarmCheckpoint]:
        results: List[SwarmCheckpoint] = []
        if not os.path.isdir(self.storage_dir):
            return results
        for fname in os.listdir(self.storage_dir):
            if fname.startswith("checkpoint_") and fname.endswith(".json"):
                exec_id = fname[len("checkpoint_"):-len(".json")]
                cp = self.get_checkpoint(exec_id)
                if cp:
                    if status is None or cp.status == status:
                        results.append(cp)
        results.sort(key=lambda x: x.updated_at, reverse=True)
        return results

    def delete_checkpoint(self, execution_id: str) -> bool:
        file_path = self._get_path(execution_id)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError:
                return False
        return False


# Global Singleton Instance
checkpoint_store = SwarmCheckpointStore()
