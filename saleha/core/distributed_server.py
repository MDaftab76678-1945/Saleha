"""
Saleha Core: Distributed GPU Swarm Server Daemon

Orchestrates multi-client autonomous task queues across centralized or remote GPU servers,
allowing engineering teams to share local LLM compute, monitor task states, and stream logs.
"""

from __future__ import annotations

import os
import time
import uuid
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class TaskQueueItem:
    task_id: str
    goal: str
    caller_id: str
    status: str             # PENDING | RUNNING | COMPLETED | FAILED
    created_at: str
    started_at: str = ""
    completed_at: str = ""
    result_output: str = ""
    error: str = ""
    logs: List[str] = field(default_factory=list)


class DistributedSwarmServer:
    """Manages distributed task scheduling and telemetry for multi-developer GPU clusters."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.tasks: Dict[str, TaskQueueItem] = {}
        self._lock = threading.RLock()
        self.is_running = False

    def submit_task(self, goal: str, caller_id: str = "developer") -> TaskQueueItem:
        """Enqueues an autonomous engineering goal."""
        with self._lock:
            tid = f"task-{uuid.uuid4().hex[:8]}"
            item = TaskQueueItem(
                task_id=tid,
                goal=goal,
                caller_id=caller_id,
                status="PENDING",
                created_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
            self.tasks[tid] = item
            return item

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result_output: str = "",
        error: str = "",
        log_message: str = ""
    ) -> Optional[TaskQueueItem]:
        """Updates lifecycle state of a queued task."""
        with self._lock:
            if task_id not in self.tasks:
                return None
            item = self.tasks[task_id]
            item.status = status
            if status == "RUNNING" and not item.started_at:
                item.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
            elif status in ("COMPLETED", "FAILED"):
                item.completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
                if result_output:
                    item.result_output = result_output
                if error:
                    item.error = error

            if log_message:
                item.logs.append(f"[{time.strftime('%H:%M:%S')}] {log_message}")

            return item

    def get_task(self, task_id: str) -> Optional[TaskQueueItem]:
        """Retrieves task state and execution logs."""
        with self._lock:
            return self.tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> List[TaskQueueItem]:
        """Lists recently submitted cluster tasks."""
        with self._lock:
            return list(self.tasks.values())[-limit:]

    def get_cluster_telemetry(self) -> Dict[str, Any]:
        """Returns compute cluster capacity and active queue statistics."""
        with self._lock:
            total = len(self.tasks)
            pending = sum(1 for t in self.tasks.values() if t.status == "PENDING")
            running = sum(1 for t in self.tasks.values() if t.status == "RUNNING")
            completed = sum(1 for t in self.tasks.values() if t.status == "COMPLETED")
            failed = sum(1 for t in self.tasks.values() if t.status == "FAILED")

            return {
                "server_host": f"{self.host}:{self.port}",
                "server_status": "ONLINE" if self.is_running else "IDLE",
                "total_tasks": total,
                "pending_tasks": pending,
                "running_tasks": running,
                "completed_tasks": completed,
                "failed_tasks": failed,
                "gpu_pool": "Local Ollama Cluster"
            }


# Global instance
distributed_server = DistributedSwarmServer()

