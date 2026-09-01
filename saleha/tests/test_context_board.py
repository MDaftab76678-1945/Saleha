"""Unit tests for the Swarm Shared Context Blackboard."""

import unittest
from saleha.core.context_board import ContextBoard, BoardEntry


class TestContextBoard(unittest.TestCase):
    """Test suite for ContextBoard swarm state sharing and pub/sub."""

    def setUp(self):
        self.board = ContextBoard(board_name="test_board")

    def test_post_and_retrieve_entries(self):
        entry = self.board.post_hypothesis("Architect", "Use sharding for multi-tenant isolation")
        self.assertIsInstance(entry, BoardEntry)
        self.assertEqual(entry.entry_type, "hypothesis")
        self.assertEqual(entry.agent_id, "Architect")

        entries = self.board.get_entries(entry_type="hypothesis")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].content, "Use sharding for multi-tenant isolation")

    def test_post_fact_and_threat(self):
        self.board.post_fact("Tester", "Latency is 4ms", {"p99": 4})
        self.board.post_threat("SecurityEngineer", "SQL injection vector in login handler", severity="HIGH")

        facts = self.board.get_entries(entry_type="fact")
        self.assertEqual(len(facts), 1)
        self.assertTrue(facts[0].verified)

        threats = self.board.get_entries(entry_type="threat")
        self.assertEqual(len(threats), 1)
        self.assertEqual(threats[0].metadata.get("severity"), "HIGH")

    def test_subscriber_notification(self):
        received_events = []

        def on_threat(entry: BoardEntry):
            received_events.append(entry)

        self.board.subscribe("threat", on_threat)
        self.board.post_threat("SecOps", "Unauthorized access attempt")

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].agent_id, "SecOps")

    def test_export_markdown(self):
        self.board.post_fact("AgentA", "Unit tests passed")
        md = self.board.export_markdown()
        self.assertIn("# Swarm Context Board: test_board", md)
        self.assertIn("Unit tests passed", md)


if __name__ == "__main__":
    unittest.main()
