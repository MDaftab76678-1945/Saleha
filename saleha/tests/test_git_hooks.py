"""Unit tests for Saleha Git Pre-Commit Security Hook Manager."""

import os
import shutil
import tempfile
import unittest
from saleha.core.git_hooks import GitHookManager, PRE_COMMIT_SCRIPT


class GitHooksTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_git_test_")
        self.git_dir = os.path.join(self.temp_dir, ".git")
        os.makedirs(self.git_dir, exist_ok=True)
        self.manager = GitHookManager(repo_path=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_install_pre_commit_hook(self):
        res = self.manager.install_pre_commit()
        self.assertTrue(res.get("success"))
        hook_path = res.get("hook_path")
        self.assertTrue(os.path.isfile(hook_path))

        with open(hook_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Saleha AI", content)
        self.assertIn("saleha sast", content)

    def test_uninstall_pre_commit_hook(self):
        self.manager.install_pre_commit()
        hook_file = os.path.join(self.git_dir, "hooks", "pre-commit")
        self.assertTrue(os.path.isfile(hook_file))

        un_res = self.manager.uninstall_pre_commit()
        self.assertTrue(un_res.get("success"))
        self.assertFalse(os.path.isfile(hook_file))

    def test_non_git_repo_fails_gracefully(self):
        empty_dir = tempfile.mkdtemp(prefix="saleha_empty_")
        mgr = GitHookManager(repo_path=empty_dir)
        try:
            res = mgr.install_pre_commit()
            self.assertFalse(res.get("success"))
            self.assertIn("Not a Git repository", res.get("error"))
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

