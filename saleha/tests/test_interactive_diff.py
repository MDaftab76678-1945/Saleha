"""Unit tests for InteractiveDiffReviewer terminal component."""

import unittest
from io import StringIO
from rich.console import Console

from saleha.cli.interactive_diff import InteractiveDiffReviewer, diff_reviewer


class InteractiveDiffTests(unittest.TestCase):

    def setUp(self):
        self.output = StringIO()
        self.test_console = Console(file=self.output, force_terminal=True, safe_box=True)
        self.reviewer = InteractiveDiffReviewer(console_instance=self.test_console)

    def test_render_diff_panel_displays_diff(self):
        old_code = "def greet():\n    return 'hello'\n"
        new_code = "def greet():\n    return 'hello world'\n"
        self.reviewer.render_diff_panel("app.py", old_code, new_code)
        text = self.output.getvalue()
        self.assertIn("Diff Review: app.py", text)
        self.assertIn("hello world", text)

    def test_prompt_review_auto_approve(self):
        old_code = "x = 1\n"
        new_code = "x = 2\n"
        approved = self.reviewer.prompt_review("config.py", old_code, new_code, auto_approve=True)
        self.assertTrue(approved)


if __name__ == "__main__":
    unittest.main()
