"""Unit tests for Saleha Polyglot Multi-Language Execution Engine."""

import unittest
from saleha.core.polyglot_executor import PolyglotExecutor, PolyglotExecutionResult


class PolyglotExecutorTests(unittest.TestCase):

    def setUp(self):
        self.executor = PolyglotExecutor(timeout=10)

    def test_detect_language(self):
        self.assertEqual(self.executor.detect_language("script.py"), "python")
        self.assertEqual(self.executor.detect_language("app.js"), "javascript")
        self.assertEqual(self.executor.detect_language("server.ts"), "typescript")
        self.assertEqual(self.executor.detect_language("main.go"), "go")
        self.assertEqual(self.executor.detect_language("App.java"), "java")
        self.assertEqual(self.executor.detect_language("lib.rs"), "rust")

    def test_execute_python_code(self):
        code = "a = 10\nb = 20\nprint(f'Sum={a+b}')"
        res = self.executor.execute(code, language="python")
        self.assertTrue(res.success)
        self.assertIn("Sum=30", res.output)
        self.assertFalse(res.blocked)

    def test_blocks_dangerous_code_via_sast(self):
        # Code with eval() must be blocked by SAST
        code = "user_input = '__import__(\"os\").system(\"ls\")'\neval(user_input)"
        res = self.executor.execute(code, language="python")
        self.assertFalse(res.success)
        self.assertTrue(res.blocked)
        self.assertIn("SEC002", res.block_reason)

    def test_blocks_javascript_eval(self):
        code = "function test() { eval('alert(1)'); }"
        res = self.executor.execute(code, language="javascript")
        self.assertFalse(res.success)
        self.assertTrue(res.blocked)
        self.assertIn("SEC101", res.block_reason)


if __name__ == "__main__":
    unittest.main()

