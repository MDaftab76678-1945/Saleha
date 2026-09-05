"""Test suite for saleha.core.agent_message_bus."""

import pytest
from saleha.core.agent_message_bus import (
    AgentMessageBus,
    AgentEvent,
    TaskAssignedEvent,
    CodeSynthesizedEvent,
    SecurityVulnerabilityEvent,
)


class TestAgentMessageBus:
    """Pub/Sub event bus for inter-agent communication."""

    @pytest.fixture
    def bus(self):
        """Fresh message bus for each test."""
        return AgentMessageBus()

    def test_subscribe_and_publish(self, bus):
        """Test basic subscribe and publish flow."""
        received = []

        def handler(event: AgentEvent):
            received.append(event)

        bus.subscribe("task_assigned", handler)
        event = TaskAssignedEvent(sender_agent="planner", task_goal="test goal")
        bus.publish(event)

        assert len(received) == 1
        assert received[0].event_type == "task_assigned"
        assert received[0].task_goal == "test goal"

    def test_unsubscribe(self, bus):
        """Test unsubscribe removes handler."""
        received = []

        def handler(event: AgentEvent):
            received.append(event)

        bus.subscribe("task_assigned", handler)
        bus.unsubscribe("task_assigned", handler)
        event = TaskAssignedEvent(sender_agent="planner", task_goal="test")
        bus.publish(event)

        assert len(received) == 0

    def test_wildcard_subscription(self, bus):
        """Test '*' wildcard receives all events."""
        received = []

        def wildcard_handler(event: AgentEvent):
            received.append(event)

        bus.subscribe("*", wildcard_handler)

        bus.publish(TaskAssignedEvent(sender_agent="p", task_goal="t"))
        bus.publish(
            CodeSynthesizedEvent(sender_agent="c", source_code="print('hi')")
        )
        bus.publish(
            SecurityVulnerabilityEvent(sender_agent="s", vulnerabilities=["xss"])
        )

        assert len(received) == 3

    def test_get_history(self, bus):
        """Test event history retrieval."""
        bus.publish(TaskAssignedEvent(sender_agent="a", task_goal="t1"))
        bus.publish(TaskAssignedEvent(sender_agent="b", task_goal="t2"))
        bus.publish(CodeSynthesizedEvent(sender_agent="c", source_code="code"))

        history = bus.get_history()
        assert len(history) == 3

        task_history = bus.get_history(event_type="task_assigned")
        assert len(task_history) == 2

    def test_history_limit(self, bus):
        """Test history respects max_history limit."""
        # Publish more than max_history (500)
        for i in range(510):
            bus.publish(TaskAssignedEvent(sender_agent="test", task_goal=f"task_{i}"))

        history = bus.get_history(limit=100)
        assert len(history) == 100
        # Should have the latest 100
        assert "509" in history[-1].task_goal

    def test_clear(self, bus):
        """Test clearing subscribers and history."""
        bus.subscribe("task_assigned", lambda e: None)
        bus.publish(TaskAssignedEvent(sender_agent="test", task_goal="t"))

        bus.clear()
        assert len(bus.get_history()) == 0
        assert len(bus._subscribers) == 0

    def test_multiple_handlers_same_event(self, bus):
        """Test multiple handlers for same event type."""
        results = [[], []]

        def handler1(e):
            results[0].append(e)

        def handler2(e):
            results[1].append(e)

        bus.subscribe("task_assigned", handler1)
        bus.subscribe("task_assigned", handler2)
        event = TaskAssignedEvent(sender_agent="test", task_goal="multi")
        bus.publish(event)

        assert len(results[0]) == 1
        assert len(results[1]) == 1

    def test_handler_exception_doesnt_break_bus(self, bus):
        """Test that one handler's exception doesn't halt other handlers."""
        results = []

        def bad_handler(e):
            raise RuntimeError("intentional error")

        def good_handler(e):
            results.append(e)

        bus.subscribe("task_assigned", bad_handler)
        bus.subscribe("task_assigned", good_handler)
        event = TaskAssignedEvent(sender_agent="test", task_goal="resilient")
        bus.publish(event)

        # Good handler should still have run
        assert len(results) == 1
