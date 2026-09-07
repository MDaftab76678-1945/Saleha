"""Unit & Integration Test Suite for Saleha v3.5.0 Ultimate Frontier Intelligence Engines:
1. MCTSSearchEngine (Test-Time Reasoning Search)
2. SpeculativeAccelerator (Dual-Engine Accelerated Stream)
3. SelfEvolvingLoop (Continuous Learning Buffer)

SWERepoFixerEngine used to be tested here. It was deleted: it returned
constants. The test below it asserted `res.tests_passing` -- the hardcoded
True -- which is why the module stayed broken for as long as it existed.
"""

import ast
import unittest

from saleha.core.mcts_search_engine import MCTSSearchEngine, mcts_search_engine, MCTSExecutionResult
from saleha.core.speculative_accelerator import SpeculativeAccelerator, speculative_accelerator, SpeculativeMetrics
from saleha.core.self_evolving_loop import SelfEvolvingLoop, self_evolving_loop, EvolvingBufferStats
from saleha.cli.chat_session import SwarmChatSession


class TestUltimateFrontierSuite(unittest.TestCase):
    def test_mcts_search_engine_explores_and_selects_winner(self):
        engine = MCTSSearchEngine(max_branches=4)
        res: MCTSExecutionResult = engine.search("Implement binary search with boundary checks")
        
        self.assertEqual(res.total_branches_explored, 4)
        self.assertGreater(res.passed_branches_count, 0)
        self.assertTrue(res.winner_code)
        self.assertGreaterEqual(res.best_score, 0.5)
        self.assertGreaterEqual(res.search_duration_ms, 0.0)
        
        # Verify winner code is valid Python AST
        tree = ast.parse(res.winner_code)
        self.assertIsNotNone(tree)

    def test_speculative_accelerator_generates_and_measures_speedup(self):
        acc = SpeculativeAccelerator(gamma_spec_depth=3)
        code, metrics = acc.generate("Fast Redis Cache Decorator")
        
        self.assertTrue(code)
        self.assertIn("execute_speculative_task", code)
        self.assertGreater(metrics.effective_tokens_per_sec, 0.0)
        self.assertGreaterEqual(metrics.acceptance_rate_pct, 50.0)
        self.assertGreaterEqual(metrics.dual_engine_speedup, 0.0)

    def test_swe_repo_fixer_is_gone(self):
        """
        `swe_repo_fixer` returned constants: two unrelated issues gave the
        identical root_cause_analysis, target files were chosen by
        `if "auth" in description`, the patch was a fixed string returning
        'RESOLVED_INVARIANT_CLEAN', and tests_passing was True with nothing
        ever run.

        The test that stood here asserted `res.tests_passing` -- the hardcoded
        True -- so it would have passed forever while the module was a
        template. Use `saleha resolve-issue`, which creates a real branch and
        runs the test command it is given.
        """
        import importlib
        with self.assertRaises(ImportError):
            importlib.import_module("saleha.core.swe_repo_fixer")

    def test_self_evolving_loop_ingests_and_buffers(self):
        loop = SelfEvolvingLoop(quality_threshold=0.80)
        code = '''def compute_sum(a: int, b: int) -> int:
    """Computes exact sum of two integers."""
    return a + b
'''
        score_res = loop.ingest_turn(
            prompt="Write a typed sum function",
            generated_code=code,
            tests_passed=True
        )
        self.assertIsNotNone(score_res)
        self.assertGreaterEqual(score_res.composite_score, 0.80)
        
        stats: EvolvingBufferStats = loop.get_stats()
        self.assertGreater(stats.total_captured_turns, 0)
        self.assertGreater(stats.qualified_high_score_turns, 0)

    def test_chat_session_handles_new_slash_commands(self):
        session = SwarmChatSession()
        self.assertTrue(session.process_command("/mcts Write a factorial function"))
        self.assertTrue(session.process_command("/speculative Build async rate limiter"))
        self.assertTrue(session.process_command("/swe-fix Resolve router zero division error"))
        self.assertTrue(session.process_command("/evolving-status"))
