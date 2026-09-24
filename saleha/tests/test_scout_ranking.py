"""System1Scout test-file ranking and the indexer parse cache."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from saleha.core.graph.codebase_indexer import CodebaseIndexer
from saleha.core.graph.system1_scout import System1Scout


class _Repo(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, rel: str, text: str) -> None:
        path = Path(self.root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class ScoutTestRankingTests(_Repo):
    def setUp(self) -> None:
        super().setUp()
        self._write("pkg/__init__.py", "")
        self._write("pkg/ledger.py", "class Ledger:\n    def record_tests(self):\n        return 1\n")
        # Mentions the symbol in a test name, but tests something else.
        self._write("tests/test_a_runner.py",
                    "def test_record_tests_flag_parsing():\n    assert True\n")
        # The real test file for pkg/ledger.py.
        self._write("tests/test_ledger.py",
                    "from pkg.ledger import Ledger\n\n\ndef test_it():\n    assert Ledger().record_tests() == 1\n")
        # A source module whose name merely starts with test_.
        self._write("pkg/test_arbiter.py", "def record_tests_arbiter(x):\n    return x\n")

    def test_the_module_named_test_file_ranks_first(self) -> None:
        d = System1Scout(self.root).scout("record_tests in Ledger is wrong")
        files = [f.replace("\\", "/") for f in d.test_files]
        self.assertEqual(files[0], "tests/test_ledger.py", files)

    def test_source_module_named_test_star_is_not_a_test(self) -> None:
        d = System1Scout(self.root).scout("record_tests in Ledger is wrong")
        self.assertNotIn("pkg/test_arbiter.py", [f.replace("\\", "/") for f in d.test_files])


class IndexerCacheTests(_Repo):
    def test_rescan_does_not_duplicate_bare_methods(self) -> None:
        self._write("a.py", "class A:\n    def run(self):\n        pass\n")
        ix = CodebaseIndexer(self.root)
        ix.scan()
        ix.scan()
        self.assertEqual(ix.find_symbol("run"), ["a.py"])
        self.assertEqual(ix.bare_method_map["run"], ["A.run"])

    def test_changed_file_is_reparsed(self) -> None:
        self._write("a.py", "def old():\n    pass\n")
        CodebaseIndexer(self.root).scan()
        time.sleep(0.01)
        self._write("a.py", "def new_name():\n    pass\n")
        os.utime(Path(self.root, "a.py"), None)
        ix = CodebaseIndexer(self.root)
        ix.scan()
        self.assertEqual(ix.find_symbol("new_name"), ["a.py"])
        self.assertEqual(ix.find_symbol("old"), [])

    def test_every_virtualenv_flavour_is_skipped(self) -> None:
        self._write(".venv_laya/lib/x.py", "def hidden():\n    pass\n")
        self._write("real.py", "def shown():\n    pass\n")
        ix = CodebaseIndexer(self.root)
        ix.scan()
        self.assertEqual(ix.find_symbol("hidden"), [])
        self.assertEqual(ix.find_symbol("shown"), ["real.py"])


if __name__ == "__main__":
    unittest.main()
