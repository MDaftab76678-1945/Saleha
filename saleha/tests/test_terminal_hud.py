"""Unit tests for Live Interactive Terminal HUD."""

from __future__ import annotations

import unittest
from saleha.cli.terminal_hud import TerminalHUD


class TerminalHUDTests(unittest.TestCase):

    def setUp(self):
        self.hud = TerminalHUD(root_dir=".")

    def test_generate_layout_creates_quadrants(self):
        layout = self.hud.generate_layout()
        self.assertIsNotNone(layout)
        child_names = [c.name for c in layout.children]
        self.assertIn("header", child_names)
        self.assertIn("main", child_names)
        self.assertIn("footer", child_names)
        self.assertIsNotNone(layout["left"]["telemetry"])
        self.assertIsNotNone(layout["right"]["codebase"])

    def test_render_once_executes_cleanly(self):
        # Should execute without throwing any exception
        try:
            self.hud.render_once()
            rendered = True
        except Exception as e:
            rendered = False
        self.assertTrue(rendered)


if __name__ == "__main__":
    unittest.main()
