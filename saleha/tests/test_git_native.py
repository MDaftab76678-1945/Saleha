"""
Unit tests for Saleha Git-Native Automation Engine.

The commit and reset paths are exercised against a throwaway repository built
in a temp directory, never the developer's own checkout -- these tests write
real commits, and running them against the working repo is exactly the kind of
accident the fixes below exist to prevent.
"""

import os
import subprocess
import tempfile
import unittest
from saleha.core.git_native import GitAutomationEngine, GitCommitResult


class GitNativeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = GitAutomationEngine(repo_path=".")

    def test_is_git_repo(self) -> None:
        is_repo = self.engine.is_git_repo()
        self.assertIsInstance(is_repo, bool)

    def test_get_current_branch(self) -> None:
        branch = self.engine.get_current_branch()
        self.assertIsInstance(branch, str)

    def test_get_status_summary(self) -> None:
        status = self.engine.get_status_summary()
        self.assertIsInstance(status, dict)
        self.assertIn("is_repo", status)

    def test_format_conventional_message_scopes(self) -> None:
        msg_core = self.engine.format_conventional_message("Implement token bucket algorithm", task_type="feat")
        self.assertTrue(msg_core.startswith("feat(core):"))
        self.assertIn("Saleha", msg_core)

        msg_api = self.engine.format_conventional_message("Add REST API endpoint for user profile", task_type="feat")
        self.assertTrue(msg_api.startswith("feat(api):"))

        msg_auth = self.engine.format_conventional_message("Fix JWT token signature verification bug", task_type="fix")
        self.assertTrue(msg_auth.startswith("fix(auth):"))

        msg_ui = self.engine.format_conventional_message("Update HTML React dark mode view", task_type="feat")
        self.assertTrue(msg_ui.startswith("feat(ui):"))

    def test_git_commit_result_dataclass(self) -> None:
        res = GitCommitResult(success=True, commit_hash="a1b2c3d", branch="main", message="feat: test")
        self.assertTrue(res.success)
        self.assertEqual(res.commit_hash, "a1b2c3d")
        self.assertEqual(res.branch, "main")

    def test_worktree_methods(self) -> None:
        from unittest.mock import patch, MagicMock
        with patch.object(self.engine, "is_git_repo", return_value=True), \
             patch.object(self.engine, "_run_git") as mock_git:
            mock_git.return_value = MagicMock(returncode=0, stdout="true", stderr="")
            ok, wt_dir, err = self.engine.create_worktree("test-task")
            self.assertTrue(ok)
            self.assertTrue(len(wt_dir) > 0)

            removed, rem_err = self.engine.remove_worktree(wt_dir)
            self.assertTrue(removed)


class VerificationClaimTests(unittest.TestCase):
    """
    `test_passed` defaulted to True, so every commit message asserted
    "Verified: Passed AST & Execution Tests" -- including commits from call
    sites that never ran a test. It is tri-state now: None means not run.
    """

    def setUp(self) -> None:
        self.engine = GitAutomationEngine(repo_path=".")

    def test_default_does_not_claim_tests_passed(self) -> None:
        msg = self.engine.format_conventional_message("do a thing")
        self.assertIn("not run", msg)
        self.assertNotIn("Passed AST & Execution Tests", msg)

    def test_true_reports_a_passing_run(self) -> None:
        msg = self.engine.format_conventional_message("x", test_passed=True)
        self.assertIn("passing", msg)

    def test_false_reports_a_failing_run(self) -> None:
        msg = self.engine.format_conventional_message("x", test_passed=False)
        self.assertIn("FAILING", msg)


class StagingSafetyTests(unittest.TestCase):
    """
    `auto_commit_task` fell back to `git add .` whenever `files` was None, and
    every caller passed None. An agent commit therefore swept up every
    unrelated uncommitted change in the user's working tree -- hand edits,
    untracked scratch files -- under a message describing the agent's task.
    """

    def setUp(self) -> None:
        self.repo = tempfile.mkdtemp(prefix="saleha_test_git_")
        self._git("init", "-q")
        self._git("config", "user.email", "t@t.t")
        self._git("config", "user.name", "t")
        self._write("base.txt", "base\n")
        self._git("add", ".")
        self._git("commit", "-qm", "base")
        self.engine = GitAutomationEngine(repo_path=self.repo)
        self._prev_mode = os.environ.get("SALEHA_APPROVAL")
        os.environ["SALEHA_APPROVAL"] = "off"

    def tearDown(self) -> None:
        if self._prev_mode is None:
            os.environ.pop("SALEHA_APPROVAL", None)
        else:
            os.environ["SALEHA_APPROVAL"] = self._prev_mode

    def _git(self, *args) -> None:
        return subprocess.run(["git"] + list(args), cwd=self.repo,
                              capture_output=True, text=True)

    def _write(self, name, content):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as fh:
            fh.write(content)

    def test_missing_file_list_is_refused_not_staged_wholesale(self) -> None:
        self._write("agent.py", "x = 1\n")
        res = self.engine.auto_commit_task(goal="add a thing")
        self.assertFalse(res.success)
        self.assertIn("no files were specified", res.error)
        # Nothing may have been committed.
        self.assertIn("agent.py", self._git("status", "--porcelain").stdout)

    def test_named_files_do_not_drag_in_unrelated_changes(self) -> None:
        self._write("agent.py", "x = 1\n")
        self._write("MY_PRIVATE_NOTES.txt", "do not commit me\n")
        res = self.engine.auto_commit_task(goal="add a thing", files=["agent.py"])
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.files_changed, ["agent.py"])
        self.assertIn("MY_PRIVATE_NOTES.txt",
                      self._git("status", "--porcelain").stdout)

    def test_stage_all_still_available_when_explicitly_requested(self) -> None:
        self._write("a.py", "x = 1\n")
        res = self.engine.auto_commit_task(goal="everything", allow_stage_all=True)
        self.assertTrue(res.success, res.error)
        self.assertIn("a.py", res.files_changed)

    def test_committed_message_reflects_the_real_verification_state(self) -> None:
        self._write("a.py", "x = 1\n")
        self.engine.auto_commit_task(goal="untested change", files=["a.py"])
        msg = self._git("log", "-1", "--pretty=%B").stdout
        self.assertIn("not run", msg)
        self.assertNotIn("Passed AST & Execution Tests", msg)

    def test_commit_deliverable_forwards_test_passed(self) -> None:
        """It used to drop the argument, so it always claimed a passing run."""
        self._write("a.py", "x = 1\n")
        self.engine.commit_deliverable(task_name="t", files=["a.py"],
                                       test_passed=False)
        self.assertIn("FAILING", self._git("log", "-1", "--pretty=%B").stdout)


class HardResetGateTests(StagingSafetyTests):
    """
    `git reset --hard` destroys every uncommitted change in the tree, not just
    the last commit. That path was completely ungated.
    """

    def test_hard_reset_is_gated_and_preserves_uncommitted_work(self) -> None:
        os.environ["SALEHA_APPROVAL"] = "always"
        self._write("precious.txt", "unsaved work\n")
        res = self.engine.rollback_last_commit(soft=False)
        # Non-TTY approval fails closed.
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("would_discard_uncommitted"), 1)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "precious.txt")))

    def test_soft_rollback_is_not_gated(self) -> None:
        self._write("a.py", "x = 1\n")
        self.engine.auto_commit_task(goal="t", files=["a.py"])
        res = self.engine.rollback_last_commit(soft=True)
        self.assertTrue(res.get("success"), res.get("error"))
        self.assertEqual(res.get("mode"), "--soft")


class CallerStagingTests(unittest.TestCase):
    """
    The three call sites all passed `files=None`, which is what made the
    `git add .` fallback reachable in practice. Assert they name their files,
    so removing that again fails the suite.
    """

    def test_refactorer_passes_the_files_it_rewrote(self) -> None:
        import inspect
        from saleha.core.multi_file_refactorer import MultiFileRefactorer
        src = inspect.getsource(MultiFileRefactorer)
        self.assertIn("files=modified_list", src)

    def test_self_healer_passes_the_files_it_patched(self) -> None:
        import inspect
        from saleha.core import self_healer
        src = inspect.getsource(self_healer)
        self.assertIn("files=healed_files", src)

    def test_orchestrator_stage_all_is_explicit(self) -> None:
        """
        The orchestrator never writes generated code to a file, so it has no
        file list. Staging everything must therefore be a deliberate flag, not
        a silent fallback.

        Checks the whole SalehaOrchestrator class source, not just
        execute_task(): the auto_commit_task() call this guards lives inside
        _handle_verified_success(), a helper execute_task() delegates to (the
        pipeline's success-recording step was extracted out to keep
        execute_task()'s own control-flow nesting under this repo's quality
        gate limit -- see quality_guard.py's COMPLEX-001 rule). The actual
        call site moving between methods on the same class is not a behavior
        change this test should be sensitive to; whether the class ever
        stages everything without being asked to is.
        """
        import inspect
        from saleha.orchestrator import SalehaOrchestrator
        src = inspect.getsource(SalehaOrchestrator)
        self.assertIn("allow_stage_all=True", src)
        # Assert what is passed, by stripping comment lines first -- the
        # explanatory comment above the call mentions the old hardcoded value.
        code_only = "\n".join(l for l in src.splitlines()
                              if not l.lstrip().startswith("#"))
        self.assertNotIn("test_passed=True", code_only)
        self.assertIn("test_passed=bool(current_test_code)", code_only)


if __name__ == "__main__":
    unittest.main()
