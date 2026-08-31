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

    def test_smart_patcher_search_replace(self):
        code = "def calc(x):\n    # TODO\n    return x\n"
        ok, patched, err = SmartPatcher.apply_search_replace(code, "    # TODO\n    return x", "    return x * 2")
        self.assertTrue(ok)
        self.assertIn("return x * 2", patched)

    def test_smart_patcher_fuzzy_matching(self):
        code = "def greet():\n    name = 'world'   \n    print(name)\n"
        # Search block has different trailing spaces
        search_b = "    name = 'world'\n    print(name)"
        replace_b = "    name = 'saleha'\n    print('hello ' + name)"
        ok, patched, err = SmartPatcher.apply_search_replace(code, search_b, replace_b)
        self.assertTrue(ok, msg=f"Fuzzy match failed: {err}")
        self.assertIn("name = 'saleha'", patched)

    def test_smart_patcher_aider_blocks(self):
        code = "def first():\n    return 1\n\ndef second():\n    return 2\n"
        diff = """<<<<<<< SEARCH
def first():
    return 1
=======
def first():
    return 100
>>>>>>>
<<<<<<< SEARCH
def second():
    return 2
=======
def second():
    return 200
>>>>>>>"""
        ok, patched, err = SmartPatcher.apply_aider_diff(code, diff)
        self.assertTrue(ok, msg=f"Aider diff failed: {err}")
        self.assertIn("return 100", patched)
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

