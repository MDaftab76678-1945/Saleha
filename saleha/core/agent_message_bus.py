"""
Saleha Core: Inter-Agent Asynchronous Event Bus & Pub/Sub Broker

Provides decoupled, typed event messaging between all 18 Python Agents:
- TaskAssignedEvent, ADRGeneratedEvent, CodeSynthesizedEvent
- SecurityVulnerabilityEvent, TestExecutionEvent, ReviewFeedbackEvent
- TokenCompressedEvent, PipelineStateChangedEvent
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Type


@dataclass
class AgentEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: str = "agent_event"
    sender_agent: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskAssignedEvent(AgentEvent):
    event_type: str = "task_assigned"
    task_goal: str = ""
    assigned_to: str = ""


@dataclass
class ADRGeneratedEvent(AgentEvent):
    event_type: str = "adr_generated"
    adr_title: str = ""
    pattern: str = ""
    components: List[str] = field(default_factory=list)


@dataclass
class CodeSynthesizedEvent(AgentEvent):
    event_type: str = "code_synthesized"
    language: str = "python"
    source_code: str = ""
    attempt_number: int = 1


@dataclass
class SecurityVulnerabilityEvent(AgentEvent):
    event_type: str = "security_vulnerability"
    cwe_identifiers: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)
    is_secure: bool = False


@dataclass
class TestExecutionEvent(AgentEvent):
    __test__ = False
    event_type: str = "test_execution"
    framework: str = "pytest"
    passed: bool = True
    tests_count: int = 0
    failure_logs: str = ""


@dataclass
class ReviewFeedbackEvent(AgentEvent):
    event_type: str = "review_feedback"
    approved: bool = True
    feedback: str = ""


@dataclass
class TokenCompressedEvent(AgentEvent):
    event_type: str = "token_compressed"
    original_tokens: int = 0
    compressed_tokens: int = 0
    savings_pct: float = 0.0


class AgentMessageBus:
    """High-throughput In-Memory Event Broker for Autonomous Multi-Agent Swarms."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[AgentEvent], None]]] = {}
        self._history: List[AgentEvent] = []
        self._max_history = 500

    def subscribe(self, event_type: str, handler: Callable[[AgentEvent], None]) -> None:
        """Subscribes an event listener to a specific event type or '*' wildcard."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[AgentEvent], None]) -> None:
        """Removes an active event listener."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: AgentEvent) -> None:
        """Dispatches an event synchronously to all registered listeners and records audit history."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # 1. Exact event_type handlers
        handlers = list(self._subscribers.get(event.event_type, []))
        # 2. Wildcard handlers
        handlers.extend(self._subscribers.get("*", []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Log error without halting the event bus dispatch loop
                pass

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> List[AgentEvent]:
        """Retrieves historical events filtered optionally by type."""
        if event_type:
            filtered = [e for e in self._history if e.event_type == event_type]
            return filtered[-limit:]
        return self._history[-limit:]

    def clear(self) -> None:
        """Clears all subscribers and history."""
        self._subscribers.clear()
        self._history.clear()


# Global Singleton Instance
message_bus = AgentMessageBus()
