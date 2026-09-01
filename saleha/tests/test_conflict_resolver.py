"""Unit tests for Autonomous Git Merge-Conflict Auto-Resolver."""

from __future__ import annotations

import unittest
from saleha.core.conflict_resolver import ConflictResolver, ConflictHunk, FileConflictResult


class ConflictResolverTests(unittest.TestCase):

    def setUp(self):
        self.resolver = ConflictResolver()

    def test_has_conflicts_detection(self):
        clean_code = "def hello():\n    return 'world'\n"
        self.assertFalse(self.resolver.has_conflicts(clean_code))

        conflict_code = "<<<<<<< HEAD\ndef a(): pass\n=======\ndef b(): pass\n>>>>>>> incoming\n"
        self.assertTrue(self.resolver.has_conflicts(conflict_code))

    def test_resolve_import_conflicts(self):
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

    def test_resolve_distinct_function_additions(self):
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

    def test_clean_file_returns_no_conflicts_status(self):
        code = "def add(x, y):\n    return x + y\n"
        res = self.resolver.resolve_content(code, file_path="math.py")
        self.assertEqual(res.conflicts_found, 0)
        self.assertEqual(res.status, "NO_CONFLICTS")

    def test_resolve_same_function_ast_merging(self):
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


if __name__ == "__main__":
    unittest.main()
