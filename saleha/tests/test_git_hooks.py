"""Unit tests for Git Pre-Commit Hook & Security Guardrail Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.git_hooks import GitHookManager


class GitHookManagerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.hooks_mgr = GitHookManager(repo_dir=self.temp_dir)
        # Create .git directory
        os.makedirs(os.path.join(self.temp_dir, ".git", "hooks"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_install_and_uninstall_hooks(self):
        ok, msg = self.hooks_mgr.install_hooks()
        self.assertTrue(ok)
        hook_p = os.path.join(self.temp_dir, ".git", "hooks", "pre-commit")
        self.assertTrue(os.path.isfile(hook_p))

        # Uninstall
        ok_un, msg_un = self.hooks_mgr.uninstall_hooks()
        self.assertTrue(ok_un)
        self.assertFalse(os.path.exists(hook_p))

    def test_run_pre_commit_check_on_clean_workspace(self):
        passed, errors = self.hooks_mgr.run_pre_commit_check()
        self.assertTrue(passed)
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
