"""Tests for the GRPO group-rollout reward scorer.

Covers real model-backed rollout generation and the group-relative-advantage
arithmetic. Does not assert on training/deployment claims -- the module
performs neither (see saleha/core/grpo_reasoning_trainer.py docstring).
"""

import os
import unittest

from saleha.core.grpo_reasoning_trainer import (
    GRPOReasoningTrainer,
    grpo_reasoning_trainer,
    GRPORollout,
    GRPOTrainingStepResult,
    GRPOTrainingSummary,
)


class TestGRPOReasoningTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join("scratch", "test_grpo_work")
        self.trainer = GRPOReasoningTrainer(group_size=3, work_dir=self.temp_dir)

    def test_train_step_generates_real_rollouts_and_advantages(self):
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

    def test_run_full_grpo_training_reports_real_rollout_count(self):
        summary: GRPOTrainingSummary = self.trainer.run_full_grpo_training(target_steps=2)
        self.assertEqual(summary.total_steps, 2)
        self.assertEqual(summary.total_rollouts, 2 * 3)
        self.assertEqual(len(summary.steps), 2)
        # No deployment or policy-update claim is made anywhere in the result.
        self.assertFalse(hasattr(summary, "deployed_model_name"))
        self.assertFalse(hasattr(summary, "red_team_vulnerabilities_neutralized"))

    def test_module_singleton_constructs(self):
        self.assertIsInstance(grpo_reasoning_trainer, GRPOReasoningTrainer)


if __name__ == "__main__":
    unittest.main()
