"""Unit & Integration Test Suite for Swarm Self-Play Arena & Stochastic Weight Averaging Engine."""

import os
import unittest

from saleha.core.swarm_self_play_arena import (
    SwarmSelfPlayArena,
    swarm_self_play_arena,
    CurriculumLevelController,
    StochasticWeightAverager,
    SWACheckpoint,
    AdversarialBattleResult,
    SwarmSelfPlaySummary,
)


class TestSwarmSelfPlayArena(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join("scratch", "test_self_play_work")
        self.arena = SwarmSelfPlayArena(work_dir=self.temp_dir)
        self.curriculum = CurriculumLevelController()

    def test_curriculum_tiers_and_prompts(self):
        for lvl in range(1, 5):
            prompts = self.curriculum.get_tier_prompts(lvl)
            self.assertGreaterEqual(len(prompts), 2)
            self.assertIn(lvl, self.curriculum.TIERS)

    def test_fight_battle_neutralizes_attacks(self):
        battle_res: AdversarialBattleResult = self.arena.fight_battle(
            battle_idx=1,
            level=3,
            prompt="Distributed Raft leader election"
        )
        self.assertEqual(battle_res.battle_id, "battle_0001")
        self.assertEqual(battle_res.curriculum_level, 3)
        self.assertGreater(battle_res.red_team_attacks_detected, 0)
        self.assertEqual(battle_res.red_team_attacks_neutralized, battle_res.red_team_attacks_detected)
        self.assertGreaterEqual(battle_res.chaos_resilience_pct, 95.0)
        self.assertGreaterEqual(battle_res.judge_pareto_reward, 0.8)

    def test_stochastic_weight_averager_fuses_checkpoints(self):
        swa = StochasticWeightAverager(top_k=3)
        swa.add_checkpoint(SWACheckpoint("ckpt_1", 1, 92.0, {}))
        swa.add_checkpoint(SWACheckpoint("ckpt_2", 2, 94.0, {}))
        swa.add_checkpoint(SWACheckpoint("ckpt_3", 3, 96.0, {}))

        report = swa.fuse_model_soup()
        self.assertEqual(report["status"], "FUSED_SUCCESS")
        self.assertEqual(len(report["checkpoints_used"]), 3)
        self.assertGreater(report["fused_master_score"], report["average_individual_score"])

    def test_run_arena_training_full_cycle(self):
        summary: SwarmSelfPlaySummary = self.arena.run_arena_training(levels_to_run=2)
        self.assertGreaterEqual(summary.total_battles_fought, 4)
        self.assertEqual(summary.curriculum_level_reached, 2)
        self.assertGreater(summary.total_attacks_neutralized, 0)
        self.assertTrue(os.path.exists(summary.fused_model_artifact_path))
