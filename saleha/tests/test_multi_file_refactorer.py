"""Unit tests for Autonomous Multi-File Atomic Refactoring Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.multi_file_refactorer import MultiFileRefactorer, FilePatchPlan, RefactorTransactionResult


class MultiFileRefactorerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.refactorer = MultiFileRefactorer(root_dir=self.temp_dir)

        # Create two interconnected python files
        self.file_a = os.path.join(self.temp_dir, "calc.py")
        with open(self.file_a, "w", encoding="utf-8") as f:
            f.write("def old_math_func(x, y):\n    return x + y\n")

        self.file_b = os.path.join(self.temp_dir, "main.py")
        with open(self.file_b, "w", encoding="utf-8") as f:
            f.write("from calc import old_math_func\n\ndef run():\n    return old_math_func(10, 20)\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plan_rename_finds_all_occurrences(self):
        ok, plans, err = self.refactorer.plan_rename("old_math_func", "new_math_func", root_dir=self.temp_dir)
        self.assertTrue(ok)
        self.assertEqual(len(plans), 2)
        # Check that diff is generated for both files
        for p in plans:
            self.assertIn("new_math_func", p.modified_code)
            self.assertGreater(p.lines_changed, 0)

    def test_apply_transaction_renames_atomically(self):
        res = self.refactorer.rename_symbol("old_math_func", "new_math_func", auto_commit=False)
        self.assertTrue(res.success)
        self.assertEqual(len(res.files_modified), 2)

        # Verify content on disk
        with open(self.file_a, "r", encoding="utf-8") as f:
            content_a = f.read()
        self.assertIn("def new_math_func(x, y):", content_a)
        self.assertNotIn("old_math_func", content_a)

        with open(self.file_b, "r", encoding="utf-8") as f:
            content_b = f.read()
        self.assertIn("from calc import new_math_func", content_b)
        self.assertIn("return new_math_func(10, 20)", content_b)

    def test_syntax_error_triggers_rollback(self):
        # Create an invalid replacement that would break python AST
        plans = [
            FilePatchPlan(
                file_path="calc.py",
                original_code="def old_math_func(x, y):\n    return x + y\n",
                modified_code="def def invalid syntax :::: 99",  # Intentional broken syntax
                diff="",
                lines_changed=1
            )
        ]
        res = self.refactorer.apply_transaction(plans, auto_commit=False)
        self.assertFalse(res.success)
        self.assertTrue(res.rollback_performed)

        # Verify disk wasn't permanently broken
        with open(self.file_a, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("def old_math_func", content)


if __name__ == "__main__":
    unittest.main()

