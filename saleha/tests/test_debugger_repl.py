"""Unit tests for Stateful AI REPL & Variable Debugger."""

import unittest
from saleha.core.debugger_repl import StatefulREPL


class StatefulREPLTests(unittest.TestCase):

    def setUp(self):
        self.repl = StatefulREPL()

    def test_execute_expression(self):
        res = self.repl.execute_statement("10 + 25")
        self.assertTrue(res.success)
        self.assertEqual(res.result_val, 35)
        self.assertEqual(res.output, "35")

    def test_execute_statement_and_persist_state(self):
        # Step 1: Assign variable
        self.repl.execute_statement("counter = 42")
        self.assertIn("counter", self.repl.globals_dict)

        # Step 2: Use variable in next expression
        res = self.repl.execute_statement("counter * 2")
        self.assertTrue(res.success)
        self.assertEqual(res.result_val, 84)

    def test_get_user_variables(self):
        self.repl.execute_statement("username = 'saleha_agent'")
        self.repl.execute_statement("scores = [100, 95, 98]")
        v_map = self.repl.get_user_variables()

        self.assertIn("username", v_map)
        self.assertEqual(v_map["username"]["type"], "str")
        self.assertIn("scores", v_map)
        self.assertEqual(v_map["scores"]["type"], "list")

    def test_syntax_error_handled_gracefully(self):
        res = self.repl.execute_statement("def bad_func( incomplete")
        self.assertFalse(res.success)
        self.assertIsNotNone(res.error)


if __name__ == "__main__":
    unittest.main()

