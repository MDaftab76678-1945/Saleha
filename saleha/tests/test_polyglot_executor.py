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

    @unittest.skipUnless(
        __import__("shutil").which("rustc"), "rustc not on PATH")
    def test_rustc_error_output_preserves_non_ascii(self):
        """Real bug found auditing this module: the rustc compile call used
        text=True with no encoding, so on this machine's default cp1252
        console a non-ASCII compiler error message came back as mojibake
        (measured: CJK identifiers in a broken program's source became
        "ä¸­æ–‡" instead of "中文" in rustc's own error text) -- CLAUDE.md
        already names this exact class of bug for polyglot_executor.py's
        Python-side subprocess.run calls (pass 36); this was the same gap in
        a sibling call the earlier pass didn't touch."""
        code = "fn main() { let 中文 = ; }"
        res = self.executor.execute(code, language="rust")
        self.assertFalse(res.success)
        self.assertIn("中文", res.error)

    def test_javac_call_requests_utf8_decoding(self):
        """Same class of bug as the rustc test above, on the Java compile
        path. No JDK is installed on this machine to run javac for real, so
        this asserts the fix at the subprocess.run call site directly."""
        import inspect
        src = inspect.getsource(self.executor._dispatch_execution)
        javac_call = src.split("if lang == \"java\":", 1)[1].split(
            "if lang == \"rust\":", 1)[0]
        self.assertIn('encoding="utf-8"', javac_call)


if __name__ == "__main__":
    unittest.main()

