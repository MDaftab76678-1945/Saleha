"""Tests for the GRPO group-rollout reward scorer.

Covers real model-backed rollout generation and the group-relative-advantage
arithmetic. Does not assert on training/deployment claims -- the module
performs neither (see saleha/core/grpo_reasoning_trainer.py docstring).
"""

import os
import tempfile
import unittest

from saleha.core.grpo_reasoning_trainer import (
    GRPOReasoningTrainer,
    grpo_reasoning_trainer,
    GRPORollout,
    GRPOTrainingStepResult,
    GRPOTrainingSummary,
)


class TestGRPOReasoningTrainer(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self._temp_dir_obj.name
        self.trainer = GRPOReasoningTrainer(group_size=3, work_dir=self.temp_dir)

    def tearDown(self) -> None:
        self._temp_dir_obj.cleanup()

    def test_lazy_work_dir_initialization(self) -> None:
        target_dir = os.path.join(self.temp_dir, "uncreated_subdir")
        trainer = GRPOReasoningTrainer(group_size=2, work_dir=target_dir)
        self.assertFalse(os.path.exists(target_dir))
        ensured = trainer._ensure_work_dir()
        self.assertEqual(ensured, target_dir)
        self.assertTrue(os.path.exists(target_dir))

    def test_score_candidate_with_formal_smt_division_guarantee(self) -> None:
        safe_code = (
            "def safe_div(a: int, b: int) -> float:\n"
            "    assert b != 0\n"
            "    return a / b\n"
        )
        unsafe_code = (
            "def unsafe_div(a: int, b: int) -> float:\n"
            "    return a / 0\n"
        )

        safe_rollout = self.trainer.score_candidate(safe_code, rollout_id="safe_1")
        unsafe_rollout = self.trainer.score_candidate(unsafe_code, rollout_id="unsafe_1")

        self.assertTrue(safe_rollout.generation_succeeded)
        self.assertTrue(safe_rollout.formal_verification_passed)
        self.assertIn("divisions proven safe", safe_rollout.formal_verification_details)

        self.assertTrue(unsafe_rollout.generation_succeeded)
        self.assertFalse(unsafe_rollout.formal_verification_passed)
        self.assertGreater(safe_rollout.total_reward, unsafe_rollout.total_reward)

    def test_score_candidate_with_formal_smt_index_bounds_guarantee(self) -> None:
        safe_index_code = (
            "def safe_access(items: list, i: int) -> int:\n"
            "    assert 0 <= i < len(items)\n"
            "    return items[i]\n"
        )
        unguarded_index_code = (
            "def unguarded_access(items: list, i: int) -> int:\n"
            "    return items[i]\n"
        )

        safe_rollout = self.trainer.score_candidate(safe_index_code, rollout_id="safe_idx")
        unguarded_rollout = self.trainer.score_candidate(unguarded_index_code, rollout_id="unguarded_idx")

        self.assertTrue(safe_rollout.formal_verification_passed)
        self.assertIn("proven in-bounds", safe_rollout.formal_verification_details)

        self.assertFalse(unguarded_rollout.formal_verification_passed)
        self.assertGreater(safe_rollout.total_reward, unguarded_rollout.total_reward)

    def test_score_candidate_empty_code(self) -> None:
        empty_rollout = self.trainer.score_candidate("", rollout_id="empty_1")
        self.assertFalse(empty_rollout.generation_succeeded)
        self.assertEqual(empty_rollout.total_reward, 0.0)
        self.assertFalse(empty_rollout.formal_verification_passed)

    def test_train_step_generates_real_rollouts_and_advantages(self) -> None:
        step_res: GRPOTrainingStepResult = self.trainer.train_step(
            step=1,
            prompt="Implement a thread-safe FIFO queue",
        )
        self.assertEqual(step_res.step, 1)
        self.assertEqual(step_res.group_size, 3)
        self.assertEqual(len(step_res.rollouts), 3)

        for rollout in step_res.rollouts:
            self.assertIsInstance(rollout, GRPORollout)
            # A rollout that failed to generate must be reported as failed,
            # not scored as if it were valid code.
            if not rollout.generation_succeeded:
                self.assertEqual(rollout.total_reward, 0.0)
                self.assertFalse(rollout.ast_valid)

        # Winner must genuinely have the highest reward in the group.
        winner = step_res.winner_rollout
        self.assertEqual(winner, step_res.rollouts[0])
        self.assertEqual(max(r.total_reward for r in step_res.rollouts), winner.total_reward)

        # Advantages must be centered on zero (group-relative, not absolute).
        advantages = [r.normalized_advantage for r in step_res.rollouts]
        self.assertAlmostEqual(sum(advantages), 0.0, places=2)

    def test_run_full_grpo_training_reports_real_rollout_count(self) -> None:
        summary: GRPOTrainingSummary = self.trainer.run_full_grpo_training(target_steps=2)
        self.assertEqual(summary.total_steps, 2)
        self.assertEqual(summary.total_rollouts, 2 * 3)
        self.assertEqual(len(summary.steps), 2)
        # No deployment or policy-update claim is made anywhere in the result.
        self.assertFalse(hasattr(summary, "deployed_model_name"))
        self.assertFalse(hasattr(summary, "red_team_vulnerabilities_neutralized"))

    def test_module_singleton_constructs(self) -> None:
        self.assertIsInstance(grpo_reasoning_trainer, GRPOReasoningTrainer)


if __name__ == "__main__":
    unittest.main()

