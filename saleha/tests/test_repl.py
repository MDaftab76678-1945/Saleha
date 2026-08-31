import unittest
from saleha.cli.repl import SalehaREPL


class REPLTests(unittest.TestCase):
    def setUp(self):
        self.repl = SalehaREPL(initial_profile="agent_sde")

    def test_repl_init(self):
        self.assertEqual(self.repl.active_profile_id, "agent_sde")
        self.assertIsNotNone(self.repl.agent)

    def test_slash_command_help_and_clear(self):
        self.repl.history.append({"role": "user", "content": "hello"})
        handled = self.repl.handle_slash_command("/clear")
        self.assertTrue(handled)
        self.assertEqual(len(self.repl.history), 0)

        handled_help = self.repl.handle_slash_command("/help")
        self.assertTrue(handled_help)

    def test_slash_command_profile_switch(self):
        handled = self.repl.handle_slash_command("/profile security_engineer")
        self.assertTrue(handled)
        self.assertEqual(self.repl.active_profile_id, "agent_security_engineer")

    def test_slash_command_tools_and_memory(self):
        self.assertTrue(self.repl.handle_slash_command("/tools"))
        self.assertTrue(self.repl.handle_slash_command("/memory"))
        self.assertTrue(self.repl.handle_slash_command("/profiles"))

    def test_slash_command_exit(self):
        self.assertTrue(self.repl.handle_slash_command("/exit"))

    def test_slash_command_symbols_status_outline(self):
        self.assertTrue(self.repl.handle_slash_command("/symbols calculate"))
        self.assertTrue(self.repl.handle_slash_command("/status"))
        self.assertTrue(self.repl.handle_slash_command("/outline setup.py"))


if __name__ == "__main__":
    unittest.main()

