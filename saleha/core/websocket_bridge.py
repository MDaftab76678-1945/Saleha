"""
Saleha Core: Live WebSocket Streaming Bridge (WebSocketBridge)

Provides real-time event streaming for VS Code Extension, Web Studio, and CLI dashboards:
1. Broadcasts agent thoughts, AST patches, tool executions, and test runs.
2. Structured JSON event payloads.
3. Thread-safe client connection management and pub/sub event routing.
"""

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Callable


@dataclass
class StreamEvent:
    """Represents a real-time event emitted during agent orchestration."""
    event_type: str  # "thinking", "tool_call", "ast_patch", "test_run", "healing", "completed"
    agent_id: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class WebSocketBridge:
    """Real-time event dispatcher and WebSocket streaming bridge."""

    def __init__(self):
        """Initializes the streaming bridge."""
        self._listeners: List[Callable[[StreamEvent], None]] = []
        self._history: List[StreamEvent] = []
        self._lock = threading.Lock()

    def register_listener(self, callback: Callable[[StreamEvent], None]):
        """Registers a callback or websocket socket sender."""
        with self._lock:
            self._listeners.append(callback)

    def broadcast(
        self,
        event_type: str,
        agent_id: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> StreamEvent:
        """Emits a live event to all registered websocket listeners and stores in history."""
        event = StreamEvent(
            event_type=event_type,
            agent_id=agent_id,
            message=message,
            payload=payload or {},
        )
        with self._lock:
            self._history.append(event)
            # Keep history bounded
            if len(self._history) > 1000:
                self._history.pop(0)
            callbacks = list(self._listeners)

        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                pass  # noqa

        return event

    def get_recent_events(self, limit: int = 50) -> List[StreamEvent]:
        """Returns recent broadcasted events."""
        with self._lock:
            return list(self._history[-limit:])

    def clear(self):
        """Clears all history and listener registrations."""
        with self._lock:
            self._listeners.clear()
            self._history.clear()


# Global singleton instance
stream_bridge = WebSocketBridge()


if __name__ == "__main__":
    _bridge = WebSocketBridge()
    _bridge.broadcast("thinking", "PlannerAgent", "Decomposing task into 3 subproblems")
