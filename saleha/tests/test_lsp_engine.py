"""Unit tests for LSPEngine diagnostic and typecheck system."""

import os
import tempfile
import unittest

from saleha.core.lsp_engine import LSPEngine, LSPDiagnostic, DiagnosticReport


class LSPEngineTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.engine = LSPEngine(root_dir=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_python_syntax_error(self):
        file_p = os.path.join(self.root, "bad_syntax.py")
        with open(file_p, "w", encoding="utf-8") as f:
            f.write("def foo(\n    print('broken')\n")

        diags = self.engine.check_file(file_p)
        self.assertGreaterEqual(len(diags), 1)
        self.assertEqual(diags[0].severity, "ERROR")
        self.assertEqual(diags[0].rule_id, "py-syntax-error")

    def test_detects_mutable_default_and_bare_except(self):
        file_p = os.path.join(self.root, "antipatterns.py")
        with open(file_p, "w", encoding="utf-8") as f:
            f.write(
                "def append_item(x, target=[]):\n"
                "    try:\n"
                "        target.append(x)\n"
                "    except:\n"
                "        pass\n"
                "    return target\n"
            )

        diags = self.engine.check_file(file_p)
        rules = [d.rule_id for d in diags]
        self.assertIn("py-mutable-default", rules)
        self.assertIn("py-bare-except", rules)

    def test_check_directory_report(self):
        file_p = os.path.join(self.root, "clean.py")
        with open(file_p, "w", encoding="utf-8") as f:
            f.write("def add(a: int, b: int) -> int:\n    return a + b\n")

        report = self.engine.check_directory(self.root)
        self.assertIsInstance(report, DiagnosticReport)
        self.assertEqual(report.error_count, 0)


if __name__ == "__main__":
    unittest.main()

