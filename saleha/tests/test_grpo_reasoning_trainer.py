"""Unit & Integration Test Suite for GRPO Reasoning & Thinking Distillation Trainer."""

import os
import unittest

from saleha.core.grpo_reasoning_trainer import (
    GRPOReasoningTrainer,
    ThoughtTraceGenerator,
    grpo_reasoning_trainer,
    GRPORollout,
    GRPOTrainingStepResult,
    GRPOTrainingSummary,
)


class TestGRPOReasoningTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join("scratch", "test_grpo_work")
        self.trainer = GRPOReasoningTrainer(group_size=6, work_dir=self.temp_dir)
        self.trace_gen = ThoughtTraceGenerator()

    def test_thought_trace_generator_emits_valid_structure(self):
        trace = self.trace_gen.generate_trace("Build async semaphore")
        self.assertTrue(trace.problem_understanding)
        self.assertGreater(len(trace.edge_case_hypotheses), 2)
        self.assertTrue(trace.invariant_safety_proof)
        self.assertTrue(trace.raw_think_tokens)
        
        full_res = trace.format_full_response("def solve(): pass")
        self.assertIn("<think>", full_res)
        self.assertIn("</think>", full_res)
        self.assertIn("```python", full_res)

    def test_grpo_train_step_computes_normalized_advantages(self):
        step_res: GRPOTrainingStepResult = self.trainer.train_step(
            step=1,
            prompt="Implement thread-safe FIFO queue"
        )
        self.assertEqual(step_res.step, 1)
        self.assertEqual(step_res.group_size, 6)
        self.assertEqual(len(step_res.rollouts), 6)
        self.assertGreaterEqual(step_res.group_mean_reward, 0.0)

        # Check winner has highest reward and positive advantage
        winner = step_res.winner_rollout
        self.assertEqual(winner, step_res.rollouts[0])
        self.assertGreaterEqual(winner.normalized_advantage, 0.0)
        self.assertTrue(winner.ast_valid)

    def test_run_full_grpo_training_completes_cycle(self):
        summary: GRPOTrainingSummary = self.trainer.run_full_grpo_training(target_steps=3)
        self.assertEqual(summary.total_steps, 3)
        self.assertEqual(summary.total_rollouts, 3 * 6)
        self.assertGreaterEqual(summary.final_mean_reward, summary.initial_mean_reward)
        self.assertGreater(summary.average_thinking_length_tokens, 100)
        self.assertTrue(summary.deployed_model_name)
