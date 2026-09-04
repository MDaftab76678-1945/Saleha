"""
Saleha Core: Structured Observability & OpenTelemetry-Compatible Session Tracer

Provides production-grade session execution tracing:
- Hierarchical spans with parent-child relationships and microsecond timing.
- Rich event logging and attribute key-value indexing.
- Seamless Python context manager support (`with tracer.span(...)`).
- Automatic ingestion bridge with `AgentMessageBus`.
- Disk export to `.saleha/traces/*.json` for post-run analysis and SWE-bench validation.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Generator, Iterator


@dataclass
class TraceEvent:
    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceSpan:
    span_id: str
    name: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "IN_PROGRESS"  # "IN_PROGRESS" | "OK" | "ERROR"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[TraceEvent] = field(default_factory=list)
    error_message: Optional[str] = None

    def finish(self, status: str = "OK", error: Optional[str] = None) -> None:
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = "ERROR" if error or status == "ERROR" else status
        if error:
            self.error_message = error

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append(TraceEvent(name=name, attributes=attributes or {}))


@dataclass
class SessionTrace:
    trace_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")
    session_name: str = "saleha_session"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration_ms: float = 0.0
    spans: Dict[str, TraceSpan] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionTracer:
    """Manages structured hierarchical spans and exports OpenTelemetry-compatible traces."""

    def __init__(self, session_name: str = "saleha_session"):
        self.current_trace = SessionTrace(session_name=session_name)
        self._active_span_stack: List[str] = []

    @property
    def trace_id(self) -> str:
        return self.current_trace.trace_id

    def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Starts a new span. If parent_id is omitted, nests under active span stack."""
        actual_parent = parent_id or (self._active_span_stack[-1] if self._active_span_stack else None)
        span_id = f"span-{uuid.uuid4().hex[:8]}"

        span = TraceSpan(
            span_id=span_id,
            name=name,
            parent_span_id=actual_parent,
            attributes=attributes or {},
        )
        self.current_trace.spans[span_id] = span
        self._active_span_stack.append(span_id)
        return span

    def end_span(
        self,
        span_id: Optional[str] = None,
        status: str = "OK",
        error: Optional[str] = None,
    ) -> Optional[TraceSpan]:
        """Ends the specified span (or the currently active top span)."""
        target_id = span_id or (self._active_span_stack[-1] if self._active_span_stack else None)
        if not target_id or target_id not in self.current_trace.spans:
            return None

        span = self.current_trace.spans[target_id]
        span.finish(status=status, error=error)

        if target_id in self._active_span_stack:
            self._active_span_stack.remove(target_id)

        return span

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator[TraceSpan, None, None]:
        """Context manager for tracing blocks of code."""
        s = self.start_span(name, attributes=attributes)
        try:
            yield s
            self.end_span(s.span_id, status="OK")
        except Exception as e:
            self.end_span(s.span_id, status="ERROR", error=str(e))
            raise

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        span_id: Optional[str] = None,
    ) -> None:
        """Appends a timestamped event to the target or top-level span."""
        target_id = span_id or (self._active_span_stack[-1] if self._active_span_stack else None)
        if target_id and target_id in self.current_trace.spans:
            self.current_trace.spans[target_id].add_event(name, attributes)

    def set_attribute(
        self,
        key: str,
        value: Any,
        span_id: Optional[str] = None,
    ) -> None:
        """Sets a key-value attribute on the target or top-level active span."""
        target_id = span_id or (self._active_span_stack[-1] if self._active_span_stack else None)
        if target_id and target_id in self.current_trace.spans:
            self.current_trace.spans[target_id].attributes[key] = value

    def attach_to_bus(self, bus: Any) -> None:
        """Subscribes to an AgentMessageBus to automatically capture all agent events."""
        def _bus_event_handler(event: Any) -> None:
            event_type = getattr(event, "event_type", "agent_event")
            sender = getattr(event, "sender_agent", "unknown")
            payload = getattr(event, "payload", {})
            self.add_event(
                name=f"bus:{event_type}",
                attributes={
                    "sender": sender,
                    "event_id": getattr(event, "event_id", ""),
                    "summary": str(payload)[:200] if payload else "",
                },
            )

        if hasattr(bus, "subscribe"):
            bus.subscribe("*", _bus_event_handler)

    def export_dict(self) -> Dict[str, Any]:
        """Serializes trace data into an OpenTelemetry-aligned dictionary."""
        end_time = time.time()
        duration_ms = round((end_time - self.current_trace.start_time) * 1000, 2)
        self.current_trace.end_time = end_time
        self.current_trace.total_duration_ms = duration_ms

        spans_list = []
        for s in self.current_trace.spans.values():
            s_dict = {
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "name": s.name,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "attributes": s.attributes,
                "error_message": s.error_message,
                "events": [
                    {"name": e.name, "timestamp": e.timestamp, "attributes": e.attributes}
                    for e in s.events
                ],
            }
            spans_list.append(s_dict)

        return {
            "trace_id": self.current_trace.trace_id,
            "session_name": self.current_trace.session_name,
            "start_time": self.current_trace.start_time,
            "end_time": end_time,
            "total_duration_ms": duration_ms,
            "span_count": len(spans_list),
            "spans": spans_list,
            "metadata": self.current_trace.metadata,
        }

    def save_to_disk(self, directory: str = ".saleha/traces") -> str:
        """Saves current trace to disk as a JSON file and returns file path."""
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, f"{self.current_trace.trace_id}.json")
        data = self.export_dict()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return file_path

    def reset(self, session_name: str = "saleha_session") -> None:
        """Resets the tracer for a new session."""
        self.current_trace = SessionTrace(session_name=session_name)
        self._active_span_stack.clear()


# Global singleton tracer
session_tracer = SessionTracer()
