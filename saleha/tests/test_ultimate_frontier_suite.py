"""Unit & Integration Test Suite for Saleha v3.5.0 Ultimate Frontier Intelligence Engines:
1. MCTSSearchEngine (Test-Time Reasoning Search)
2. SpeculativeAccelerator (Dual-Engine Accelerated Stream)
3. SWERepoFixerEngine (Multi-File Repo Bug Resolution)
4. SelfEvolvingLoop (Continuous Learning Buffer)
"""

import ast
import unittest

from saleha.core.mcts_search_engine import MCTSSearchEngine, mcts_search_engine, MCTSExecutionResult
from saleha.core.speculative_accelerator import SpeculativeAccelerator, speculative_accelerator, SpeculativeMetrics
from saleha.core.swe_repo_fixer import SWERepoFixerEngine, swe_repo_fixer, SWERepoFixResult
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

    def test_swe_repo_fixer_resolves_multi_file_issue(self):
        fixer = SWERepoFixerEngine()
        res: SWERepoFixResult = fixer.resolve_issue(
            issue_title="Fix JWT auth token validation and session expiry",
            issue_body="Tokens with expired timestamps are not properly rejected in gateway."
        )
        self.assertTrue(res.tests_passing)
        self.assertGreaterEqual(res.total_files_affected, 2)
        self.assertTrue(res.unified_git_diff)
        self.assertIn("--- a/", res.unified_git_diff)
        self.assertIn("+++ b/", res.unified_git_diff)

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
