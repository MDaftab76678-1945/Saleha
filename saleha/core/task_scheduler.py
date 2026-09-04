"""TaskSchedulerEngine: JSON-persisted 5-field cron task registry.

Previously this claimed "WAL-Persisted" in its own docstring but was a plain
in-memory dict (lost on restart), never parsed the cron_expression it stored,
and trigger_task_now() faked success with a hardcoded duration_ms=16.4
without running anything. Now: tasks persist to disk, next_run is computed
from a real 5-field cron parser, and trigger_task_now() actually executes the
goal via TeamOrchestrator and records a real TaskHistory entry.

There is still no autonomous background loop firing tasks on their own --
that needs a long-lived process. run_due_tasks() executes whatever is
currently due; call it periodically (e.g. from a cron job or `saleha
scheduler run-due`) rather than expecting tasks to fire themselves.
"""

from __future__ import annotations
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_SCHEDULE_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "scheduled_tasks.json")


@dataclass
class ScheduledTask:
    task_id: str
    cron_expression: str
    goal: str
    agent_target: str = "Swarm"
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_run_timestamp: Optional[float] = None
    next_run_timestamp: Optional[float] = None
    total_executions: int = 0
    last_status: str = "PENDING"


def _field_matches(value: int, field_expr: str, max_value: int) -> bool:
    if field_expr == "*":
        return True
    for part in field_expr.split(","):
        if part.startswith("*/"):
            step = int(part[2:])
            if step > 0 and value % step == 0:
                return True
        elif "-" in part:
            lo, hi = part.split("-")
            if int(lo) <= value <= int(hi):
                return True
        elif part.isdigit() and int(part) == value:
            return True
    return False


def cron_matches(cron_expression: str, when: datetime) -> bool:
    """Real 5-field (min hour day month weekday) cron matching -- no library
    dependency, but genuinely parses and evaluates the expression rather than
    ignoring it."""
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, day, month, weekday = parts
    return (
        _field_matches(when.minute, minute, 59)
        and _field_matches(when.hour, hour, 23)
        and _field_matches(when.day, day, 31)
        and _field_matches(when.month, month, 12)
        and _field_matches(when.weekday(), weekday, 6)
    )


def _next_run_after(cron_expression: str, after: float, horizon_minutes: int = 60 * 24 * 8) -> Optional[float]:
    """Scans forward minute-by-minute (bounded to horizon_minutes, default 8
    days) for the next timestamp the cron expression matches. Simple and
    correct rather than clever; a scheduler with thousands of tasks would
    need a smarter approach, this one doesn't have that scale."""
    start = datetime.fromtimestamp(after).replace(second=0, microsecond=0)
    for i in range(1, horizon_minutes + 1):
        candidate = datetime.fromtimestamp(start.timestamp() + i * 60)
        if cron_matches(cron_expression, candidate):
            return candidate.timestamp()
    return None


class TaskSchedulerEngine:
    def __init__(self, path: str = DEFAULT_SCHEDULE_PATH):
        self.path = path
        self._tasks: Dict[str, ScheduledTask] = {}
        self._load()
        if not self._tasks:
            self._init_default_schedules()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._tasks = {tid: ScheduledTask(**data) for tid, data in raw.items()}
        except (OSError, json.JSONDecodeError, TypeError):
            self._tasks = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({tid: asdict(t) for tid, t in self._tasks.items()}, f, indent=2)
        os.replace(tmp, self.path)

    def _init_default_schedules(self):
        self.register_task(
            cron_expression="0 * * * *",
            goal="Autonomous Repository Security SAST & Invariant Audit",
            agent_target="SecurityGuardAgent",
        )
        self.register_task(
            cron_expression="*/30 * * * *",
            goal="Scan Active Dependencies for Upstream Vulnerability Advisories",
            agent_target="DevOpsAgent",
        )

    def register_task(self, cron_expression: str, goal: str, agent_target: str = "Swarm") -> ScheduledTask:
        clean_cron = cron_expression.strip()
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = ScheduledTask(
            task_id=task_id,
            cron_expression=clean_cron,
            goal=goal.strip(),
            agent_target=agent_target,
            next_run_timestamp=_next_run_after(clean_cron, time.time()),
        )
        self._tasks[task_id] = task
        self._save()
        return task

    def list_tasks(self) -> List[ScheduledTask]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
        return False

    def trigger_task_now(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Actually runs the task's goal through the orchestrator, rather
        than fabricating a SUCCESS result with a fixed duration."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        from saleha.core.team_orchestrator import TeamOrchestrator
        from saleha.core.task_history import TaskHistory

        start = time.perf_counter()
        try:
            result = TeamOrchestrator().run_team_workflow(task.goal)
            success = result.success
            code = result.code
        except Exception:
            success = False
            code = ""
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        task.total_executions += 1
        task.last_run_timestamp = time.time()
        task.last_status = "SUCCESS" if success else "FAILED"
        task.next_run_timestamp = _next_run_after(task.cron_expression, task.last_run_timestamp)
        self._save()

        try:
            TaskHistory().log(goal=task.goal, model="scheduler", success=success, code=code, task_id=task.task_id)
        except Exception:
            pass

        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.last_status,
            "executed_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.last_run_timestamp)),
            "duration_ms": duration_ms,
        }

    def run_due_tasks(self) -> List[Dict[str, Any]]:
        """Executes every enabled task whose next_run_timestamp has passed.
        No process runs this automatically -- call it periodically (CLI/cron)."""
        now = time.time()
        results = []
        for task in list(self._tasks.values()):
            if task.enabled and task.next_run_timestamp and task.next_run_timestamp <= now:
                outcome = self.trigger_task_now(task.task_id)
                if outcome:
                    results.append(outcome)
        return results


task_scheduler = TaskSchedulerEngine()
