"""Unit tests for Saleha Git-Native Automation Engine."""

import os
import unittest
from saleha.core.git_native import GitAutomationEngine, GitCommitResult


class GitNativeTests(unittest.TestCase):

    def setUp(self):
        self.engine = GitAutomationEngine(repo_path=".")

    def test_is_git_repo(self):
        is_repo = self.engine.is_git_repo()
        self.assertIsInstance(is_repo, bool)

    def test_get_current_branch(self):
        branch = self.engine.get_current_branch()
        self.assertIsInstance(branch, str)

    def test_get_status_summary(self):
        status = self.engine.get_status_summary()
        self.assertIsInstance(status, dict)
        self.assertIn("is_repo", status)

    def test_format_conventional_message_scopes(self):
        msg_core = self.engine.format_conventional_message("Implement token bucket algorithm", task_type="feat")
        self.assertTrue(msg_core.startswith("feat(core):"))
        self.assertIn("Saleha AI", msg_core)

        msg_api = self.engine.format_conventional_message("Add REST API endpoint for user profile", task_type="feat")
        self.assertTrue(msg_api.startswith("feat(api):"))

        msg_auth = self.engine.format_conventional_message("Fix JWT token signature verification bug", task_type="fix")
        self.assertTrue(msg_auth.startswith("fix(auth):"))

        msg_ui = self.engine.format_conventional_message("Update HTML React dark mode view", task_type="feat")
        self.assertTrue(msg_ui.startswith("feat(ui):"))

    def test_git_commit_result_dataclass(self):
        res = GitCommitResult(success=True, commit_hash="a1b2c3d", branch="main", message="feat: test")
        self.assertTrue(res.success)
        self.assertEqual(res.commit_hash, "a1b2c3d")
        self.assertEqual(res.branch, "main")

    def test_worktree_methods(self):
        from unittest.mock import patch, MagicMock
        with patch.object(self.engine, "is_git_repo", return_value=True), \
             patch.object(self.engine, "_run_git") as mock_git:
            mock_git.return_value = MagicMock(returncode=0, stdout="true", stderr="")
            ok, wt_dir, err = self.engine.create_worktree("test-task")
            self.assertTrue(ok)
            self.assertTrue(len(wt_dir) > 0)

            removed, rem_err = self.engine.remove_worktree(wt_dir)
            self.assertTrue(removed)


if __name__ == "__main__":
    unittest.main()
