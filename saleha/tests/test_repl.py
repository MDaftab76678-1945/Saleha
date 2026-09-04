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

    def test_slash_command_soul_and_souls(self):
        self.assertTrue(self.repl.handle_slash_command("/souls"))
        self.assertTrue(self.repl.handle_slash_command("/soul artisan"))
        from saleha.core.soul_engine import soul_engine
        self.assertEqual(soul_engine.get_active_soul_name(), "artisan")

    def test_slash_command_cost_and_compact(self):
        self.assertTrue(self.repl.handle_slash_command("/cost"))
        for i in range(10):
            self.repl.history.append({"role": "user", "content": f"msg {i}"})
        self.assertTrue(self.repl.handle_slash_command("/compact"))
        self.assertTrue(len(self.repl.history) <= 5)

    def test_slash_command_mode(self):
        self.assertTrue(self.repl.handle_slash_command("/mode auto"))
        self.assertEqual(self.repl.security_mode, "auto")
        self.assertTrue(self.repl.handle_slash_command("/mode guard"))
        self.assertEqual(self.repl.security_mode, "guard")
        self.assertTrue(self.repl.handle_slash_command("/mode readonly"))
        self.assertEqual(self.repl.security_mode, "readonly")

    def test_slash_command_search(self):
        self.assertTrue(self.repl.handle_slash_command("/search"))
        self.assertTrue(self.repl.handle_slash_command("/search calculate"))


if __name__ == "__main__":
    unittest.main()

