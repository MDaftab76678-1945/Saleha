"""Unit tests for Autonomous Git Merge-Conflict Auto-Resolver."""

from __future__ import annotations

import unittest
from saleha.core.conflict_resolver import ConflictResolver


class ConflictResolverTests(unittest.TestCase):

    def setUp(self) -> None:
        self.resolver = ConflictResolver()

    def test_has_conflicts_detection(self) -> None:
        clean_code = "def hello():\n    return 'world'\n"
        self.assertFalse(self.resolver.has_conflicts(clean_code))

        conflict_code = "<<<<<<< HEAD\ndef a(): pass\n=======\ndef b(): pass\n>>>>>>> incoming\n"
        self.assertTrue(self.resolver.has_conflicts(conflict_code))

    def test_single_line_hunk_keeps_its_indentation(self) -> None:
        """Real bug found auditing this module: `"\\n".join(lines).strip()`
        strips the joined STRING's whitespace, which for a single-line hunk
        (the most common real conflict shape) strips that line's own
        leading indentation -- nothing else in the string protects it.
        Confirmed by direct probe before fixing: a hunk changing one
        indented line inside a function body resolved to MANUAL_REQUIRED
        (correctly refused, since the de-indented line is a syntax error)
        instead of the clean single-line merge it should have been."""
        code = (
            "def process(x):\n"
            "    y = x * 2\n"
            "<<<<<<< HEAD\n"
            "    z = y + 1\n"
            "=======\n"
            "    z = y + 2\n"
            ">>>>>>> incoming\n"
            "    return z\n"
        )
        res = self.resolver.resolve_content(code, file_path="app.py")
        self.assertTrue(res.is_valid_ast, res.resolved_content)
        self.assertEqual(res.status, "RESOLVED")
        self.assertIn("    z = y", res.resolved_content)
        self.assertIn("    return z", res.resolved_content)

    def test_resolve_import_conflicts(self) -> None:
        code = """<<<<<<< HEAD
import os
import sys
=======
import os
import json
>>>>>>> feature-branch
def run(): pass
"""
        res = self.resolver.resolve_content(code, file_path="app.py")
        self.assertTrue(res.is_valid_ast)
        self.assertEqual(res.status, "RESOLVED")
        self.assertIn("import os", res.resolved_content)
        self.assertIn("import sys", res.resolved_content)
        self.assertIn("import json", res.resolved_content)
        self.assertNotIn("<<<<<<<", res.resolved_content)

    def test_resolve_distinct_function_additions(self) -> None:
        code = """<<<<<<< HEAD
def feature_alpha():
    return 'alpha'
=======
def feature_beta():
    return 'beta'
>>>>>>> feature-branch
"""
        res = self.resolver.resolve_content(code, file_path="features.py")
        self.assertTrue(res.is_valid_ast)
        self.assertEqual(res.status, "RESOLVED")
        self.assertIn("def feature_alpha", res.resolved_content)
        self.assertIn("def feature_beta", res.resolved_content)

    def test_clean_file_returns_no_conflicts_status(self) -> None:
        code = "def add(x, y):\n    return x + y\n"
        res = self.resolver.resolve_content(code, file_path="math.py")
        self.assertEqual(res.conflicts_found, 0)
        self.assertEqual(res.status, "NO_CONFLICTS")

    def test_resolve_same_function_ast_merging(self) -> None:
        code = """<<<<<<< HEAD
def authenticate(username, password):
    if not username:
        raise ValueError("Username empty")
    return verify(username, password)
=======
def authenticate(username, password, token=None):
    if not password:
        raise ValueError("Password empty")
    return verify(username, password)
>>>>>>> incoming
"""
        res = self.resolver.resolve_content(code, file_path="auth.py")
        self.assertTrue(res.is_valid_ast)
        self.assertEqual(res.status, "RESOLVED")
        self.assertIn("Username empty", res.resolved_content)
        self.assertIn("Password empty", res.resolved_content)

    def test_merge_without_return_invents_no_return(self) -> None:
        """Neither side returns here -- the merge must not invent a return
        statement no side wrote (previously a hardcoded "return True")."""
        merged = self.resolver._resolve_ast_function_conflict(
            "def f(a):\n    x = a + 1\n",
            "def f(a):\n    y = a + 2\n",
        )
        self.assertIsNotNone(merged)
        self.assertNotIn("return", merged)
        self.assertIn("x = a + 1", merged)
        self.assertIn("y = a + 2", merged)


if __name__ == "__main__":
    unittest.main()
