"""A4: Session persistence & resume tests."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from saleha.core.session_store import SessionStore, SessionState
from saleha.orchestrator import SalehaOrchestrator, OrchestrationResult


class SessionStoreTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(os.path.join(tmp, "s.json"))
            st = SessionState(goal="build cache", attempts=2,
                              current_code="print(1)", status="in_progress")
            store.save(st)
            loaded = store.load()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.goal, "build cache")
            self.assertEqual(loaded.attempts, 2)
            self.assertEqual(loaded.status, "in_progress")

    def test_clear_removes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(os.path.join(tmp, "s.json"))
            store.save(SessionState(goal="x", current_code="y"))
            store.clear()
            self.assertIsNone(store.load())

    def test_load_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(os.path.join(tmp, "none.json"))
            self.assertIsNone(store.load())


class ResumeFlowTests(unittest.TestCase):
    def _orchestrator(self):
        orch = SalehaOrchestrator(model="test-model", max_healing_attempts=3)

        # Planner/Coder ko kabhi call NAHI hona chahiye resume par
        orch.planner.create_plan = MagicMock(
            side_effect=AssertionError("planner must not run on resume"))
        orch.coder.generate_code = MagicMock(
            side_effect=AssertionError("coder must not run on resume"))

        # Static checks pass; verifier executes code successfully
        res = MagicMock()
        res.passed = True
        orch.tester.test_code = MagicMock(return_value=res)
        review = MagicMock()
        review.approved = True
        review.feedback = ""
        orch.reviewer.review_code = MagicMock(return_value=review)
        exec_res = MagicMock()
        exec_res.success = True
        exec_res.blocked = False
        exec_res.block_reason = None
        exec_res.error = ""
        exec_res.output = "ok"
        orch.verifier.execute = MagicMock(return_value=exec_res)
        return orch

    def _no_memory(self):
        """Global ~/.saleha memory se isolation -- recall kabhi hit na ho."""
        mem = MagicMock()
        mem.recall.return_value = None
        mem.remember.return_value = None
        return mem

    def test_resume_skips_planning_and_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            import saleha.core.session_store as ss_module
            store = SessionStore(os.path.join(tmp, "s.json"))
            store.save(SessionState(
                goal="interrupted task",
                profile="",
                attempts=1,
                max_attempts=3,
                current_code="value = 42\nprint(value)",
                status="in_progress",
            ))

            orch = self._orchestrator()
            with patch.object(ss_module, "session_store", store), \
                 patch("saleha.orchestrator.memory_store", self._no_memory()), \
                 patch("saleha.core.git_native.git_engine") as mock_git:
                mock_git.is_git_repo.return_value = False
                result = orch.execute_task("", resume_session=True)

            self.assertTrue(result.success, msg=result.log)
            self.assertIn("RESUME", result.log)
            self.assertEqual(result.final_code, "value = 42\nprint(value)")
            # Checkpoint complete hoke clear-mark ho gaya
            final = store.load()
            self.assertEqual(final.status, "completed")

    def test_resume_without_session_fails_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            import saleha.core.session_store as ss_module
            store = SessionStore(os.path.join(tmp, "empty.json"))
            orch = SalehaOrchestrator(model="m")
            with patch.object(ss_module, "session_store", store):
                result = orch.execute_task("", resume_session=True)
            self.assertFalse(result.success)
            self.assertIn("resumable", result.log.lower())

    def test_normal_run_writes_checkpoint_and_completes_it(self):
        """Non-resume flow bhi checkpoints likhta hai (crash recovery ke liye)."""
        with tempfile.TemporaryDirectory() as tmp:
            import saleha.core.session_store as ss_module
            store = SessionStore(os.path.join(tmp, "s.json"))

            orch = self._orchestrator()
            with patch.object(ss_module, "session_store", store), \
                 patch.object(orch.planner, "create_plan") as mock_plan, \
                 patch("saleha.orchestrator.memory_store", self._no_memory()), \
                 patch("saleha.core.git_native.git_engine") as mock_git:
                plan = MagicMock()
                plan.success = True
                plan.steps = ["step1"]
                plan.recommendation = "OK"
                plan.raw_response = "ok"
                plan.complexity_score = 0.0
                mock_plan.return_value = plan

                code_res = MagicMock()
                code_res.success = True
                code_res.code = "print('generated')"
                code_res.error = ""
                code_res.model_used = "m"
                orch.coder.generate_code = MagicMock(return_value=code_res)
                mock_git.is_git_repo.return_value = False

                result = orch.execute_task("fresh goal")

            self.assertTrue(result.success, msg=result.log)
            final = store.load()
            self.assertIsNotNone(final)
            self.assertEqual(final.status, "completed")


if __name__ == "__main__":
    unittest.main()
