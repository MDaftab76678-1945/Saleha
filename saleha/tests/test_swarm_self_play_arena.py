"""Unit & integration tests for the Swarm Self-Play Arena and reward aggregator."""

import os
import unittest

from saleha.core.swarm_self_play_arena import (
    SwarmSelfPlayArena,
    CurriculumLevelController,
    RewardAggregator,
    RoundReward,
    AdversarialBattleResult,
    SwarmSelfPlaySummary,
)


class TestSwarmSelfPlayArena(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = os.path.join("scratch", "test_self_play_work")
        self.arena = SwarmSelfPlayArena(work_dir=self.temp_dir)
        self.curriculum = CurriculumLevelController()

    def test_curriculum_tiers_and_prompts(self) -> None:
        for lvl in range(1, 5):
            prompts = self.curriculum.get_tier_prompts(lvl)
            self.assertGreaterEqual(len(prompts), 2)
            self.assertIn(lvl, self.curriculum.TIERS)

    def test_fight_battle_runs_real_pipeline(self) -> None:
        """The battle must call the coder, then score the code it actually
        produced -- not a template. Under SALEHA_TEST_MODE the coder uses the
        MockProvider, so we assert on structure, not on fabricated constants."""
        battle_res: AdversarialBattleResult = self.arena.fight_battle(
            battle_idx=1, level=3, prompt="Distributed Raft leader election"
        )
        self.assertEqual(battle_res.battle_id, "battle_0001")
        self.assertEqual(battle_res.curriculum_level, 3)
        # The candidate came from the coder agent, and its model is recorded.
        self.assertTrue(battle_res.coder_model_used)
        # Reward is a real 0-1 combination, not a baked-in >= 0.8.
        self.assertGreaterEqual(battle_res.judge_pareto_reward, 0.0)
        self.assertLessEqual(battle_res.judge_pareto_reward, 1.0)
        # Unresolved findings can never exceed total findings.
        self.assertLessEqual(
            battle_res.security_findings_unresolved, battle_res.security_findings
        )

    def test_failed_generation_is_reported_not_scored(self) -> None:
        """If the coder returns nothing, the round is marked failed and a hard
        negative, with zeroed scores -- not a fake passing result."""
        arena = SwarmSelfPlayArena(work_dir=self.temp_dir)

        class _EmptyCoder:
            def generate_code(self, *_a, **_k):
                class _R:
                    success = False
                    code = ""
                    model_used = "stub"
                return _R()

        arena._coder = _EmptyCoder()  # type: ignore[assignment]
        res = arena.fight_battle(battle_idx=7, level=1, prompt="anything")
        self.assertFalse(res.coder_succeeded)
        self.assertTrue(res.hard_negative_mined)
        self.assertEqual(res.judge_pareto_reward, 0.0)
        self.assertEqual(res.chaos_resilience_pct, 0.0)

    def test_reward_aggregator_takes_top_k_mean(self) -> None:
        agg = RewardAggregator(top_k=3)
        agg.add_round(RoundReward("r1", 1, 92.0))
        agg.add_round(RoundReward("r2", 2, 94.0))
        agg.add_round(RoundReward("r3", 3, 96.0))
        agg.add_round(RoundReward("r4", 4, 10.0))  # dropped: not in top 3

        report = agg.aggregate()
        self.assertEqual(report["status"], "AGGREGATED")
        self.assertEqual(len(report["rounds_used"]), 3)
        # Mean of 92, 94, 96 -- no "+1.8 ensemble boost".
        self.assertAlmostEqual(report["aggregate_reward_score"], 94.0, places=2)

    def test_reward_aggregator_empty(self) -> None:
        report = RewardAggregator().aggregate()
        self.assertEqual(report["status"], "EMPTY")
        self.assertEqual(report["aggregate_reward_score"], 0.0)

    def test_run_arena_full_cycle_writes_manifest(self) -> None:
        summary: SwarmSelfPlaySummary = self.arena.run_arena_training(levels_to_run=2)
        self.assertGreaterEqual(summary.total_battles_fought, 4)
        self.assertEqual(summary.curriculum_level_reached, 2)
        self.assertTrue(os.path.isdir(summary.run_artifact_path))
        self.assertTrue(
            os.path.isfile(os.path.join(summary.run_artifact_path, "run_manifest.json"))
        )
        self.assertGreaterEqual(summary.aggregate_reward_score, 0.0)


if __name__ == "__main__":
    unittest.main()
