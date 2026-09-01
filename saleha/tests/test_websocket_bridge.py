"""Unit tests for Live WebSocket Streaming Bridge."""

import unittest
from saleha.core.websocket_bridge import WebSocketBridge, StreamEvent


class TestWebSocketBridge(unittest.TestCase):
    """Test suite for WebSocketBridge event broadcasting."""

    def setUp(self):
        self.bridge = WebSocketBridge()

    def test_broadcast_and_receive_events(self):
        received_events = []

        def on_event(e: StreamEvent):
            received_events.append(e)

        self.bridge.register_listener(on_event)
        event = self.bridge.broadcast("thinking", "CoderAgent", "Writing unit tests", {"tests": 5})

        self.assertIsInstance(event, StreamEvent)
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].event_type, "thinking")
        self.assertEqual(received_events[0].agent_id, "CoderAgent")

    def test_get_recent_events(self):
        self.bridge.broadcast("step1", "A", "M1")
        self.bridge.broadcast("step2", "B", "M2")
        recent = self.bridge.get_recent_events(limit=5)
        self.assertEqual(len(recent), 2)


if __name__ == "__main__":
    unittest.main()
