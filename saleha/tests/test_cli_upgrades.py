"""
Unit tests for Saleha CLI Supercharger upgrades:
- Interactive patch reviewer ([y]/[n]/[d]/[e])
- /repair command
- /pr command
- /debate command
- /diff command
"""

import unittest
from unittest.mock import patch
from saleha.cli.repl import SalehaREPL


class TestCLIUpgrades(unittest.TestCase):
    def setUp(self):
        self.repl = SalehaREPL(model="mock")

    def test_slash_command_debate(self):
        handled = self.repl.handle_slash_command("/debate Zero-Copy Deserialization Engine")
        self.assertTrue(handled)

    def test_slash_command_debate_no_arg(self):
        handled = self.repl.handle_slash_command("/debate")
        self.assertTrue(handled)

    def test_slash_command_repair(self):
        failing_output = 'File "saleha/example.py", line 42, in test_fn\nZeroDivisionError: division by zero'
        handled = self.repl.handle_slash_command(f"/repair {failing_output}")
        self.assertTrue(handled)

    def test_slash_command_pr(self):
        handled = self.repl.handle_slash_command("/pr Implement Async Memory Cache")
        self.assertTrue(handled)

    def test_slash_command_diff(self):
        handled = self.repl.handle_slash_command("/diff")
        self.assertTrue(handled)

    def test_review_patch_auto_mode(self):
        self.repl.security_mode = "auto"
        res = self.repl.review_patch("src/main.py", "a = 1", "a = 2", "Update variable")
        self.assertTrue(res)

    def test_review_patch_readonly_mode(self):
        self.repl.security_mode = "readonly"
        res = self.repl.review_patch("src/main.py", "a = 1", "a = 2", "Update variable")
        self.assertFalse(res)

    @patch("rich.console.Console.input", return_value="y")
    def test_review_patch_guard_mode_accept(self, mock_input):
        self.repl.security_mode = "guard"
        res = self.repl.review_patch("src/main.py", "a = 1", "a = 2", "Update variable")
        self.assertTrue(res)

    @patch("rich.console.Console.input", return_value="n")
    def test_review_patch_guard_mode_reject(self, mock_input):
        self.repl.security_mode = "guard"
        res = self.repl.review_patch("src/main.py", "a = 1", "a = 2", "Update variable")
        self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
