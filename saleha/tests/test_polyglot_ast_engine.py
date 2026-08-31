"""Unit tests for Native Polyglot AST & Concrete Syntax Tree Engine."""

from __future__ import annotations

import unittest
from saleha.core.polyglot_ast_engine import PolyglotASTEngine, PolyglotSymbol


class PolyglotASTEngineTests(unittest.TestCase):

    def setUp(self):
        self.engine = PolyglotASTEngine()

    def test_detect_language(self):
        self.assertEqual(self.engine.detect_language("server.py"), "python")
        self.assertEqual(self.engine.detect_language("App.tsx"), "typescript")
        self.assertEqual(self.engine.detect_language("main.go"), "go")
        self.assertEqual(self.engine.detect_language("lib.rs"), "rust")
        self.assertEqual(self.engine.detect_language("Service.java"), "java")

    def test_parse_python_ast(self):
        code = "class Calculator:\n    def add(self, a, b):\n        return a + b\n"
        syms = self.engine.parse_python("calc.py", code)
        self.assertEqual(len(syms), 2)
        names = [s.name for s in syms]
        self.assertIn("Calculator", names)
        self.assertIn("add", names)

    def test_parse_javascript_typescript(self):
        code = "export async function fetchUser(id: string) {}\nexport class UserService {}\nconst logEvent = () => {}"
        syms = self.engine.parse_javascript_typescript("api.ts", code)
        self.assertEqual(len(syms), 3)
        names = [s.name for s in syms]
        self.assertIn("fetchUser", names)
        self.assertIn("UserService", names)
        self.assertIn("logEvent", names)

    def test_parse_go_functions_and_structs(self):
        code = "type Server struct {}\nfunc (s *Server) Start() {}\nfunc HandleRequest() {}"
        syms = self.engine.parse_go("server.go", code)
        self.assertEqual(len(syms), 3)
        names = [s.name for s in syms]
        self.assertIn("Server", names)
        self.assertIn("Start", names)
        self.assertIn("HandleRequest", names)

    def test_parse_rust_functions_and_structs(self):
        code = "pub struct Config {}\npub async fn run_server() {}"
        syms = self.engine.parse_rust("main.rs", code)
        self.assertEqual(len(syms), 2)
        names = [s.name for s in syms]
        self.assertIn("Config", names)
        self.assertIn("run_server", names)

    def test_parse_java_classes(self):
        code = "public class PaymentGateway {\n    public void processPayment() {}\n}"
        syms = self.engine.parse_java("PaymentGateway.java", code)
        self.assertGreater(len(syms), 0)
        self.assertEqual(syms[0].name, "PaymentGateway")


if __name__ == "__main__":
    unittest.main()

