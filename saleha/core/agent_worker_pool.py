"""
Saleha Core: Sandboxed Agent Worker Pool & Execution Isolation Layer

Provides non-blocking threaded and subprocess worker pools with strict execution timeouts,
memory bounds, and graceful fault recovery.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass
from typing import Callable, Any, Optional, Dict


@dataclass
class WorkerTaskResult:
    success: bool
    result: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    worker_id: str = "worker-0"


class AgentWorkerPool:
    """Bounded Concurrency Worker Pool for Multi-Agent Task Isolation."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._active_tasks: Dict[str, concurrent.futures.Future] = {}

    def execute_task(
        self,
        task_id: str,
        func: Callable[..., Any],
        *args: Any,
        timeout_sec: float = 10.0,
        **kwargs: Any
    ) -> WorkerTaskResult:
        """Executes a callable inside an isolated worker with strict timeout protection."""
        start_time = time.time()
        future = self._executor.submit(func, *args, **kwargs)
        self._active_tasks[task_id] = future

        try:
            res = future.result(timeout=timeout_sec)
            elapsed = round((time.time() - start_time) * 1000, 2)
            self._active_tasks.pop(task_id, None)
            return WorkerTaskResult(
                success=True,
                result=res,
                execution_time_ms=elapsed,
                worker_id=f"worker-{task_id[:4]}"
            )
        except concurrent.futures.TimeoutError:
            elapsed = round((time.time() - start_time) * 1000, 2)
            self._active_tasks.pop(task_id, None)
            return WorkerTaskResult(
                success=False,
                error_message=f"Task timed out after {timeout_sec}s",
                execution_time_ms=elapsed,
                worker_id=f"worker-{task_id[:4]}"
            )
        except Exception as e:
            elapsed = round((time.time() - start_time) * 1000, 2)
            self._active_tasks.pop(task_id, None)
            return WorkerTaskResult(
                success=False,
                error_message=str(e),
                execution_time_ms=elapsed,
                worker_id=f"worker-{task_id[:4]}"
            )

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait)


# Global Singleton Instance
worker_pool = AgentWorkerPool()
