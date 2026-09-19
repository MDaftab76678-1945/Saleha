"""Unit Tests for AST-Based ChangeImpactAnalyzer.

Verifies change impact analysis, false-positive resistance for short symbols,
scoped class/method diffing, affected test discovery, and blast radius calculation.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from saleha.core.change_impact import ChangeImpactAnalyzer, ImpactReport


class TestChangeImpactAnalyzer(unittest.TestCase):
    """Test suite for ChangeImpactAnalyzer blast radius estimation."""

    def setUp(self) -> None:
        self.tmp_dir: str = tempfile.mkdtemp()
        self.analyzer: ChangeImpactAnalyzer = ChangeImpactAnalyzer()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_file(self, rel_path: str, content: str) -> str:
        full_path = os.path.join(self.tmp_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    def test_false_positive_resistance_for_short_symbols(self) -> None:
        """Verify that modifying 'add' does not match 'address' or comments."""
        old_math = "def add(a: int, b: int) -> int:\n    return a + b\n"
        new_math = "def add(a: int, b: int) -> int:\n    return (a + b) * 1\n"
        math_file = self._write_file("math_ops.py", new_math)

        # File containing substring 'add' in other words, but never calling add()
        other_code = '''
class AddressBook:
    """Class holding address entries."""
    def __init__(self) -> None:
        self.address = "123 Main St"
        # added yesterday
        self.additional_info = "Suite 100"
'''
        self._write_file("contacts.py", other_code)

        # Real caller file that actually calls add()
        caller_code = '''
from math_ops import add

def compute() -> int:
    return add(10, 20)
'''
        self._write_file("calculator.py", caller_code)

        report: ImpactReport = self.analyzer.analyze(
            old_math, new_math, file_path=math_file, repo_root=self.tmp_dir
        )

        self.assertIn("add", report.changed_symbols)
        # calculator.py must be an affected caller
        self.assertIn("calculator.py", report.affected_callers)
        # contacts.py must NOT be an affected caller (no false positive on address/added)
        self.assertNotIn("contacts.py", report.affected_callers)

    def test_scoped_method_diffing(self) -> None:
        """Verify that changes to class methods are accurately captured with scoping."""
        old_code = '''
class PaymentProcessor:
    def process_transaction(self, amount: float) -> bool:
        return amount > 0

    def refund(self, amount: float) -> bool:
        return True
'''
        new_code = '''
class PaymentProcessor:
    def process_transaction(self, amount: float) -> bool:
        if amount <= 0:
            raise ValueError("Negative amount")
        return True

    def refund(self, amount: float) -> bool:
        return True
'''
        file_p = self._write_file("payment.py", new_code)
        report: ImpactReport = self.analyzer.analyze(
            old_code, new_code, file_path=file_p, repo_root=self.tmp_dir
        )

        self.assertTrue(
            any("process_transaction" in s for s in report.changed_symbols)
        )
        self.assertFalse(
            any("refund" in s for s in report.changed_symbols)
        )

    def test_deleted_symbol_detection(self) -> None:
        """Verify that deleted functions are marked with DELETED: prefix."""
        old_code = "def legacy_func() -> None:\n    pass\n\ndef keep_func() -> None:\n    pass\n"
        new_code = "def keep_func() -> None:\n    pass\n"

        file_p = self._write_file("deprecated.py", new_code)
        report: ImpactReport = self.analyzer.analyze(
            old_code, new_code, file_path=file_p, repo_root=self.tmp_dir
        )

        self.assertIn("DELETED:legacy_func", report.changed_symbols)
        self.assertNotIn("keep_func", report.changed_symbols)

    def test_affected_tests_detection(self) -> None:
        """Verify that test files referencing changed symbols are detected."""
        old_code = "def parse_token(raw: str) -> str:\n    return raw.strip()\n"
        new_code = "def parse_token(raw: str) -> str:\n    return raw.strip().lower()\n"
        file_p = self._write_file("tokenizer.py", new_code)

        test_code = '''
import unittest
from tokenizer import parse_token

class TestTokenizer(unittest.TestCase):
    def test_parse(self) -> None:
        self.assertEqual(parse_token(" ABC "), "abc")
'''
        self._write_file(os.path.join("tests", "test_tokenizer.py"), test_code)

        report: ImpactReport = self.analyzer.analyze(
            old_code, new_code, file_path=file_p, repo_root=self.tmp_dir
        )

        self.assertIn("test_tokenizer.py", report.affected_test_files)

    def test_blast_radius_and_risk_thresholds(self) -> None:
        """Verify blast radius range and risk level mapping."""
        old_code = "def func_a() -> None:\n    pass\n"
        new_code = "def func_a() -> None:\n    print('a')\n"
        file_p = self._write_file("a.py", new_code)

        report: ImpactReport = self.analyzer.analyze(
            old_code, new_code, file_path=file_p, repo_root=self.tmp_dir
        )

        self.assertGreaterEqual(report.blast_radius, 0)
        self.assertLessEqual(report.blast_radius, 100)
        self.assertIn(report.risk_level, ["low", "medium", "high", "critical"])
        self.assertIsInstance(report.summary, str)

        # No change must yield 0 changed symbols
        no_change_report = self.analyzer.analyze(
            old_code, old_code, file_path=file_p, repo_root=self.tmp_dir
        )
        self.assertEqual(len(no_change_report.changed_symbols), 0)

    def test_dependency_graph_coupling(self) -> None:
        """Verify that passing dependency_graph detects impacted dependents."""
        class MockDepGraph:
            def get_impacted_files(self, file_path: str) -> list[str]:
                return ["client_a.py", "client_b.py"]

        old_code = "def serve() -> None:\n    pass\n"
        new_code = "def serve() -> None:\n    print('v2')\n"
        file_p = self._write_file("server.py", new_code)

        report: ImpactReport = self.analyzer.analyze(
            old_code, new_code, file_path=file_p, repo_root=self.tmp_dir, dependency_graph=MockDepGraph()
        )

        self.assertEqual(report.impacted_dependents, ["client_a.py", "client_b.py"])
        self.assertIn("2 dependent module(s) impacted", report.summary)

    def test_ast_cache_coupling(self) -> None:
        """Verify that passing ast_cache triggers invalidation on analyzed files."""
        class MockASTCache:
            def __init__(self) -> None:
                self.invalidated_files: list[str] = []
                self.invalidated_deps: list[str] = []

            def invalidate(self, file_path: str) -> bool:
                self.invalidated_files.append(file_path)
                return True

            def invalidate_dependents(self, file_path: str, dep_graph: object) -> list[str]:
                self.invalidated_deps.append(file_path)
                return ["dep.py"]

        mock_cache = MockASTCache()
        old_code = "def run() -> None:\n    pass\n"
        new_code = "def run() -> None:\n    return None\n"
        file_p = self._write_file("runner.py", new_code)

        self.analyzer.analyze(
            old_code, new_code, file_path=file_p, repo_root=self.tmp_dir, ast_cache=mock_cache
        )

        self.assertIn(file_p, mock_cache.invalidated_files)

    def test_private_symbol_damping(self) -> None:
        """Verify that modifying only private symbols yields lower blast radius than public symbols."""
        old_pub = "def calculate() -> int:\n    return 1\n"
        new_pub = "def calculate() -> int:\n    return 2\n"
        pub_file = self._write_file("public_mod.py", new_pub)

        old_priv = "def _internal_helper() -> int:\n    return 1\n"
        new_priv = "def _internal_helper() -> int:\n    return 2\n"
        priv_file = self._write_file("private_mod.py", new_priv)

        pub_report: ImpactReport = self.analyzer.analyze(
            old_pub, new_pub, file_path=pub_file, repo_root=self.tmp_dir
        )
        priv_report: ImpactReport = self.analyzer.analyze(
            old_priv, new_priv, file_path=priv_file, repo_root=self.tmp_dir
        )

        self.assertLessEqual(priv_report.blast_radius, pub_report.blast_radius)

    def test_empty_content_edge_cases(self) -> None:
        """Verify handling of new files (empty old content) and deleted files (empty new content)."""
        file_p = self._write_file("new_mod.py", "def brand_new(): pass\n")

        # Addition of new file
        add_report: ImpactReport = self.analyzer.analyze(
            "", "def brand_new() -> None:\n    pass\n", file_path=file_p, repo_root=self.tmp_dir
        )
        self.assertIn("brand_new", add_report.changed_symbols)

        # Deletion of file
        del_report: ImpactReport = self.analyzer.analyze(
            "def brand_new() -> None:\n    pass\n", "", file_path=file_p, repo_root=self.tmp_dir
        )
        self.assertIn("DELETED:brand_new", del_report.changed_symbols)


if __name__ == "__main__":
    unittest.main()
