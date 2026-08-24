"""Unit tests for Polyglot Multi-Language Indexer & SAST Security Scanner."""

import os
import unittest
from saleha.core.polyglot_indexer import PolyglotIndexer
from saleha.core.security_scanner import ASTSecurityScanner


class PolyglotMultiLangTests(unittest.TestCase):

    def setUp(self):
        self.indexer = PolyglotIndexer(root_dir=".")
        self.scanner = ASTSecurityScanner()

    def test_language_detection(self):
        self.assertEqual(self.indexer.detect_language("app.js"), "javascript")
        self.assertEqual(self.indexer.detect_language("server.ts"), "typescript")
        self.assertEqual(self.indexer.detect_language("main.go"), "go")
        self.assertEqual(self.indexer.detect_language("App.java"), "java")
        self.assertEqual(self.indexer.detect_language("lib.rs"), "rust")
        self.assertEqual(self.indexer.detect_language("script.py"), "python")
        self.assertEqual(self.indexer.detect_language("unknown.xyz"), "unknown")

    def test_javascript_sast_eval_and_xss_detection(self):
        js_vuln_code = """
        function runCode(userInput) {
            eval(userInput);
            document.write(userInput);
        }
        """
        vulns = self.scanner.scan_code(js_vuln_code, filename="test.js")
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC101", rule_ids)
        self.assertIn("SEC102", rule_ids)

    def test_go_sast_sql_injection_detection(self):
        go_vuln_code = """
        package main
        import "fmt"
        func getUser(id string) {
            db.Query(fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", id))
        }
        """
        vulns = self.scanner.scan_code(go_vuln_code, filename="main.go")
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC201", rule_ids)

    def test_java_sast_deserialization_detection(self):
        java_vuln_code = """
        public class Loader {
            public Object load(InputStream in) throws Exception {
                ObjectInputStream ois = new ObjectInputStream(in);
                return ois.readObject();
            }
        }
        """
        vulns = self.scanner.scan_code(java_vuln_code, filename="Loader.java")
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC202", rule_ids)

    def test_rust_sast_unsafe_block_detection(self):
        rust_vuln_code = """
        fn dangerous_op(ptr: *const i32) -> i32 {
            unsafe {
                *ptr
            }
        }
        """
        vulns = self.scanner.scan_code(rust_vuln_code, filename="lib.rs")
        rule_ids = [v.rule_id for v in vulns]
        self.assertIn("SEC301", rule_ids)


if __name__ == "__main__":
    unittest.main()

