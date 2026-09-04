"""
Unit tests for Saleha Session Tracer (saleha/core/session_tracer.py).
"""

import json
import os
import tempfile
import pytest
from saleha.core.session_tracer import SessionTracer, TraceSpan, session_tracer
from saleha.core.agent_message_bus import AgentMessageBus, TaskAssignedEvent


def test_tracer_span_lifecycle():
    tracer = SessionTracer("test_session")
    span = tracer.start_span("compile_code", attributes={"compiler": "ast"})
    assert span.status == "IN_PROGRESS"
    assert span.parent_span_id is None

    finished = tracer.end_span(span.span_id, status="OK")
    assert finished is not None
    assert finished.status == "OK"
    assert finished.duration_ms >= 0.0


def test_tracer_nested_spans():
    tracer = SessionTracer("nested_session")
    root = tracer.start_span("root_task")
    child = tracer.start_span("child_task")

    assert child.parent_span_id == root.span_id

    tracer.end_span(child.span_id)
    tracer.end_span(root.span_id)

    exported = tracer.export_dict()
    assert exported["span_count"] == 2
    assert exported["spans"][1]["parent_span_id"] == exported["spans"][0]["span_id"]


def test_tracer_context_manager():
    tracer = SessionTracer("context_session")

    with tracer.span("successful_step") as s:
        tracer.set_attribute("key", "val")
        tracer.add_event("checkpoint_1")

    assert s.status == "OK"
    assert s.attributes["key"] == "val"
    assert len(s.events) == 1

    with pytest.raises(ValueError):
        with tracer.span("failing_step") as fs:
            raise ValueError("Something went wrong")

    assert fs.status == "ERROR"
    assert "Something went wrong" in fs.error_message


def test_tracer_message_bus_integration():
    tracer = SessionTracer("bus_session")
    bus = AgentMessageBus()
    tracer.attach_to_bus(bus)

    with tracer.span("bus_monitored_task") as s:
        bus.publish(TaskAssignedEvent(task_goal="Build TTC module", assigned_to="SalehaEngineer"))

    # Verify event was captured in the active span
    assert any("task_assigned" in e.name for e in s.events)


def test_tracer_save_to_disk():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracer = SessionTracer("disk_session")
        with tracer.span("file_step"):
            tracer.set_attribute("disk", True)

        path = tracer.save_to_disk(directory=tmpdir)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["session_name"] == "disk_session"
        assert data["span_count"] == 1
