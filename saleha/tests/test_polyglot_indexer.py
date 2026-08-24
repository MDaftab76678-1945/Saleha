import unittest
import tempfile
import os
from saleha.core.polyglot_indexer import PolyglotIndexer
from saleha.core.security_scanner import ASTSecurityScanner


class PolyglotIndexerTests(unittest.TestCase):
    def setUp(self):
        self.indexer = PolyglotIndexer()
        self.scanner = ASTSecurityScanner()

    def test_polyglot_language_detection(self):
        self.assertEqual(self.indexer.detect_language("server.ts"), "typescript")
        self.assertEqual(self.indexer.detect_language("main.go"), "go")
        self.assertEqual(self.indexer.detect_language("App.java"), "java")
        self.assertEqual(self.indexer.detect_language("lib.rs"), "rust")
        self.assertEqual(self.indexer.detect_language("script.py"), "python")

    def test_parse_js_ts_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath = os.path.join(tmp, "service.ts")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("""
import { Router } from 'express';
export interface UserPayload { id: string; }
export class UserService {
    async getUser(id: string) {}
}
export const calculateTax = (amount: number) => amount * 0.18;
""")
            summary = self.indexer.index_file(fpath)
            self.assertIsNotNone(summary)
            self.assertEqual(summary.language, "typescript")
            sym_names = [s.name for s in summary.symbols]
            self.assertIn("UserPayload", sym_names)
            self.assertIn("UserService", sym_names)
            self.assertIn("calculateTax", sym_names)

    def test_polyglot_security_scanning_js_and_go(self):
        js_code = 'const evil = eval("2 + 2");\nconst html = <div dangerouslySetInnerHTML={{__html: userInput}} />;\n'
        js_vulns = self.scanner.scan_code(js_code, filename="component.jsx")
        rule_ids = [v.rule_id for v in js_vulns]
        self.assertIn("SEC101", rule_ids)
        self.assertIn("SEC102", rule_ids)

        go_code = 'func getUser(db *sql.DB, id string) { db.Query(fmt.Sprintf("SELECT * FROM users WHERE id = \'%s\'", id)) }\n'
        go_vulns = self.scanner.scan_code(go_code, filename="repo.go")
        self.assertTrue(any(v.rule_id == "SEC201" for v in go_vulns))


if __name__ == "__main__":
    unittest.main()

