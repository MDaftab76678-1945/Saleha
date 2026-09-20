import unittest
import os
import tempfile
import json
from click.testing import CliRunner

from saleha.core.codebase_indexer import CodebaseIndexer, SmartPatcher
from saleha.cli.commands import cli


class CodebaseIndexerTests(unittest.TestCase):
    def test_ast_symbol_extraction(self) -> None:
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

    def test_smart_patcher_unified_diff(self) -> None:
        orig = "def add(a, b):\n    return a + b\n"
        mod = "def add(a, b):\n    # Fast add\n    return a + b\n"
        diff = SmartPatcher.create_unified_diff(orig, mod, "math.py")
        self.assertIn("+    # Fast add", diff)

    def test_smart_patcher_search_replace(self) -> None:
        code = "def calc(x):\n    # TODO\n    return x\n"
        ok, patched, err = SmartPatcher.apply_search_replace(code, "    # TODO\n    return x", "    return x * 2")
        self.assertTrue(ok)
        self.assertIn("return x * 2", patched)

    def test_smart_patcher_fuzzy_matching(self) -> None:
        code = "def greet():\n    name = 'world'   \n    print(name)\n"
        # Search block has different trailing spaces
        search_b = "    name = 'world'\n    print(name)"
        replace_b = "    name = 'saleha'\n    print('hello ' + name)"
        ok, patched, err = SmartPatcher.apply_search_replace(code, search_b, replace_b)
        self.assertTrue(ok, msg=f"Fuzzy match failed: {err}")
        self.assertIn("name = 'saleha'", patched)

    def test_smart_patcher_fuzzy_match_spans_a_blank_line(self) -> None:
        """Real bug found auditing this module: fuzzy_find_block's blank-line
        skip logic compared search_lines[k] (k indexes trimmed_search, a
        shorter list with blanks removed) instead of trimmed_search[k], so a
        blank line appearing at the same position in both search and source
        fell through to the match check, found "" != trimmed_search[k], and
        aborted the whole match -- even though the blank line was a genuine
        match, not a mismatch."""
        code = "def foo():\n    x = 1\n\n    y = 2\n    return x + y\n"
        search_b = "x = 1\n\ny = 2"
        replace_b = "x = 10\n\ny = 20"
        ok, patched, err = SmartPatcher.apply_search_replace(code, search_b, replace_b)
        self.assertTrue(ok, msg=f"blank-line fuzzy match failed: {err}")
        self.assertIn("    x = 10", patched)
        self.assertIn("    y = 20", patched)
        self.assertIn("    return x + y", patched)

    def test_smart_patcher_fuzzy_match_preserves_source_indentation(self) -> None:
        """Real bug: mode 3 matches lines regardless of indentation but then
        spliced in the replacement's own literal leading whitespace verbatim
        -- a tab-indented source line patched with a 4-space search/replace
        block came back with the tab silently replaced by 4 spaces, an
        unrequested reformat of a line the caller never asked to touch."""
        code = "def foo():\n\treturn 1\n\tprint(1)\n"
        ok, patched, err = SmartPatcher.apply_search_replace(
            code, "    return 1", "    return 2")
        self.assertTrue(ok, msg=f"match failed: {err}")
        self.assertIn("\treturn 2", patched)
        self.assertIn("\tprint(1)", patched, "next line must not be glued on")

    def test_smart_patcher_fuzzy_match_replace_without_trailing_newline(self) -> None:
        """Real bug: a replace_block with no trailing newline (a very
        plausible thing for a model to write) got spliced back in as-is,
        gluing the next real source line onto the end of the last
        replacement line instead of starting a new line."""
        code = "def foo():\n\treturn 1\n\tprint(1)\n"
        ok, patched, err = SmartPatcher.apply_search_replace(
            code, "    return 1", "    return 2")  # no trailing \n on replace
        self.assertTrue(ok, msg=f"match failed: {err}")
        lines = patched.splitlines()
        self.assertIn("\treturn 2", lines)
        self.assertIn("\tprint(1)", lines)

    def test_smart_patcher_aider_blocks(self) -> None:
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
    def test_smart_patcher_syntax_validation(self) -> None:
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

    def test_find_symbol_resolves_bare_method_name(self) -> None:
        """Measured against a real repo bug: find_symbols on a bare test
        method name ("test_super_len_with_tell") returned "not found",
        even though the method exists, because only "ClassName.method"
        was registered -- a model reading a failing test's name out of
        pytest output has no way to know its class name yet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = os.path.join(tmpdir, "test_sample.py")
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write(
                    "import unittest\n\n"
                    "class TestSuperLen(unittest.TestCase):\n"
                    "    def test_super_len_with_tell(self):\n"
                    "        pass\n"
                )
            indexer = CodebaseIndexer(root_dir=tmpdir)
            indexer.scan()

            self.assertEqual(
                indexer.find_symbol("test_super_len_with_tell"),
                ["test_sample.py"],
            )
            # The qualified form must keep working too.
            self.assertEqual(
                indexer.find_symbol("TestSuperLen.test_super_len_with_tell"),
                ["test_sample.py"],
            )

    def test_find_symbol_bare_lookup_does_not_shadow_top_level_function(self) -> None:
        """A bare-method fallback must only fire on an exact-match miss, so
        a top-level function is never masked by a same-named method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = os.path.join(tmpdir, "sample.py")
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write(
                    "def helper():\n"
                    "    pass\n\n"
                    "class Other:\n"
                    "    def helper(self):\n"
                    "        pass\n"
                )
            indexer = CodebaseIndexer(root_dir=tmpdir)
            indexer.scan()

            self.assertEqual(indexer.find_symbol("helper"), ["sample.py"])

    def test_find_symbol_bare_method_across_multiple_classes(self) -> None:
        """setUp() exists on many TestCase subclasses -- the fallback must
        return every file that defines it, not just the first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in (1, 2):
                with open(os.path.join(tmpdir, f"test_{i}.py"), "w",
                         encoding="utf-8") as f:
                    f.write(
                        "import unittest\n\n"
                        f"class T{i}(unittest.TestCase):\n"
                        "    def setUp(self):\n"
                        "        pass\n"
                    )
            indexer = CodebaseIndexer(root_dir=tmpdir)
            indexer.scan()

            files = set(indexer.find_symbol("setUp"))
            self.assertEqual(files, {"test_1.py", "test_2.py"})

    def test_find_symbol_unknown_name_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "sample.py"), "w",
                     encoding="utf-8") as f:
                f.write("def real_function():\n    pass\n")
            indexer = CodebaseIndexer(root_dir=tmpdir)
            indexer.scan()

            self.assertEqual(indexer.find_symbol("nonexistent_symbol"), [])

    def test_cli_scan_json(self) -> None:
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

