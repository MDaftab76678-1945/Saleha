import unittest
import os
import tempfile
import json
from click.testing import CliRunner

from saleha.core.codebase_indexer import CodebaseIndexer, SmartPatcher
from saleha.cli.commands import cli


class CodebaseIndexerTests(unittest.TestCase):
    def test_ast_symbol_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = os.path.join(tmpdir, "sample.py")
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write('''"""Sample Module Docstring."""
import os
from datetime import datetime

class OrderService:
    """Handles order processing."""
    def process_order(self, order_id: str) -> bool:
        """Process an order."""
        return True

def standalone_helper(x: int) -> int:
    return x * 2
''')
            indexer = CodebaseIndexer(root_dir=tmpdir)
            files = indexer.scan()
            self.assertEqual(len(files), 1)

            f_index = files["sample.py"]
            self.assertEqual(f_index.docstring, "Sample Module Docstring.")
            self.assertIn("os", f_index.imports)
            self.assertIn("datetime", f_index.from_imports)
            self.assertIn("OrderService", f_index.classes)
            self.assertIn("process_order", f_index.classes["OrderService"].methods)
            self.assertIn("standalone_helper", f_index.functions)

            summary = indexer.get_summary()
            self.assertEqual(summary["total_files"], 1)
            self.assertEqual(summary["total_classes"], 1)
            self.assertEqual(summary["total_functions"], 2)

    def test_smart_patcher_unified_diff(self):
        orig = "def add(a, b):\n    return a + b\n"
        mod = "def add(a, b):\n    # Fast add\n    return a + b\n"
        diff = SmartPatcher.create_unified_diff(orig, mod, "math.py")
        self.assertIn("+    # Fast add", diff)

    def test_smart_patcher_syntax_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "broken.py")
            with open(target, "w", encoding="utf-8") as f:
                f.write("def ok(): pass\n")

            # Invalid python syntax should fail safely
            res = SmartPatcher.apply_patch(target, "def broken( invalid syntax")
            self.assertFalse(res["success"])
            self.assertIn("syntax error", res["error"].lower())

            # Valid python syntax should succeed
            res_ok = SmartPatcher.apply_patch(target, "def ok():\n    return 42\n")
            self.assertTrue(res_ok["success"])
            with open(target, "r", encoding="utf-8") as f:
                self.assertIn("return 42", f.read())

    def test_cli_scan_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.py")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("class A: pass\n")

            res = CliRunner().invoke(cli, ["scan", tmpdir, "--json"])
            self.assertEqual(res.exit_code, 0)
            payload = json.loads(res.output)
            self.assertIn("summary", payload)
            self.assertEqual(payload["summary"]["total_classes"], 1)


if __name__ == "__main__":
    unittest.main()

