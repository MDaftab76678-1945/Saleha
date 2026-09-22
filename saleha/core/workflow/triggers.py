"""
Saleha Workflow Engine: Codebase-Native & Autonomous System Triggers.

Extends n8n's basic webhook/cron triggers with deep engineering triggers:
- GitCommitTrigger: triggers on repository changes
- TestFailureTrigger: triggers automated self-healing when tests fail
- ComplexityTrigger: triggers refactoring workflows when AST complexity spikes
- FileWatchTrigger: triggers on local source file modifications
- WebhookTrigger & CronTrigger: standard network & time automation
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from saleha.core.workflow.nodes import NodeStatus, WorkflowExecutionContext, WorkflowNode


class TriggerNode(WorkflowNode):
    """Base contract for workflow trigger nodes."""

    def __init__(
        self,
        node_id: str,
        title: str,
        trigger_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(node_id, title, node_type=f"trigger_{trigger_type}", depends_on=[], config=config)
        self.trigger_type = trigger_type

    def is_triggered(self, event_data: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if the trigger condition is met."""
        return True

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        payload = self.config.get("event_payload", {})
        self.status = NodeStatus.COMPLETED
        self.outputs = {"triggered": True, "payload": payload, "type": self.trigger_type}
        return self.outputs


class CronTrigger(TriggerNode):
    """Evaluates 5-field standard cron schedules."""

    def __init__(self, node_id: str, title: str, cron_expression: str) -> None:
        super().__init__(node_id, title, trigger_type="cron", config={"cron_expression": cron_expression})
        self.cron_expression = cron_expression

    def is_triggered(self, event_data: Optional[Dict[str, Any]] = None) -> bool:
        from saleha.core.task_scheduler import cron_matches
        when = (event_data or {}).get("timestamp") or datetime.now()
        return cron_matches(self.cron_expression, when)


class WebhookTrigger(TriggerNode):
    """Receives HTTP Webhook events with path and payload validation."""

    def __init__(self, node_id: str, title: str, path: str, secret_token: Optional[str] = None) -> None:
        super().__init__(
            node_id,
            title,
            trigger_type="webhook",
            config={"path": path, "secret_token": secret_token},
        )
        self.path = path
        self.secret_token = secret_token

    def is_triggered(self, event_data: Optional[Dict[str, Any]] = None) -> bool:
        if not event_data:
            return False
        req_path = event_data.get("path", "")
        if req_path != self.path:
            return False
        if self.secret_token:
            token = event_data.get("token") or event_data.get("headers", {}).get("X-Webhook-Token")
            return token == self.secret_token
        return True


class FileWatchTrigger(TriggerNode):
    """Triggers when target source files are modified or created."""

    def __init__(self, node_id: str, title: str, file_paths: List[str]) -> None:
        super().__init__(node_id, title, trigger_type="file_watch", config={"file_paths": file_paths})
        self.file_paths = file_paths
        self.last_hashes: Dict[str, str] = {}

    def _compute_hash(self, path: str) -> str:
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return ""

    def is_triggered(self, event_data: Optional[Dict[str, Any]] = None) -> bool:
        changed = False
        current_hashes: Dict[str, str] = {}
        for p in self.file_paths:
            h = self._compute_hash(p)
            current_hashes[p] = h
            if p in self.last_hashes and self.last_hashes[p] != h:
                changed = True
        self.last_hashes = current_hashes
        return changed


class TestFailureTrigger(TriggerNode):
    """Triggers an autonomous healing workflow when test execution fails."""

    __test__ = False

    def __init__(self, node_id: str, title: str) -> None:
        super().__init__(node_id, title, trigger_type="test_failure")

    def is_triggered(self, event_data: Optional[Dict[str, Any]] = None) -> bool:
        if not event_data:
            return False
        exit_code = event_data.get("exit_code", 0)
        failed_tests = event_data.get("failed_tests", 0)
        return exit_code != 0 or failed_tests > 0


class ComplexityTrigger(TriggerNode):
    """Triggers refactoring when cyclomatic complexity exceeds threshold."""

    def __init__(self, node_id: str, title: str, max_allowed_complexity: float = 8.0) -> None:
        super().__init__(
            node_id,
            title,
            trigger_type="complexity",
            config={"max_allowed_complexity": max_allowed_complexity},
        )
        self.max_allowed_complexity = max_allowed_complexity

    def is_triggered(self, event_data: Optional[Dict[str, Any]] = None) -> bool:
        if not event_data:
            return False
        score = float(event_data.get("complexity_score", 0.0))
        return score > self.max_allowed_complexity
