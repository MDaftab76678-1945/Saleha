"""Unit tests for Full-Screen Interactive Terminal UI Workspace."""

import unittest
from saleha.cli.tui_app import SalehaTUI


class TestSalehaTUI(unittest.TestCase):
    """Test suite for SalehaTUI layout generation and command handling."""

    def setUp(self):
        self.tui = SalehaTUI(model="mock")

    def test_build_layout_structure(self):
        layout = self.tui.build_layout()
        self.assertIsNotNone(layout)
        child_names = [c.name for c in layout.children]
        self.assertIn("header", child_names)
        self.assertIn("body", child_names)
        self.assertIn("footer", child_names)

    def test_chat_history_appends(self):
        self.tui.chat_history.append("User test message")
        self.assertIn("User test message", self.tui.chat_history[-1])


if __name__ == "__main__":
    unittest.main()
