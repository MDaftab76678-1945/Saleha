"""
Unit and integration tests for Monte Carlo Tree Search (MCTS) Engine.
Validates UCB1 exploration policy, multi-depth expansion, rollout evaluation, and backpropagation.
"""

from __future__ import annotations

import ast
import pytest

from saleha.core.mcts_search_engine import MCTSExecutionResult, MCTSNode, MCTSSearchEngine


class TestMCTSSearchEngine:
    def setup_method(self) -> None:
        self.engine = MCTSSearchEngine(max_branches=4, max_depth=1)

    def test_ucb1_policy_unvisited_returns_infinity(self) -> None:
        node = MCTSNode(node_id="leaf_1", code_candidate="x = 1", depth=1)
        assert node.visits == 0
        score = node.ucb1(total_parent_visits=10)
        assert score == float("inf")

    def test_ucb1_policy_visited_computes_tradeoff(self) -> None:
        node = MCTSNode(node_id="leaf_2", code_candidate="x = 2", depth=1, visits=4, total_reward=3.0)
        score = node.ucb1(total_parent_visits=16, exploration_weight=1.414)
        assert 0.0 < score < float("inf")
        # exploitation = 3/4 = 0.75, exploration = 1.414 * sqrt(ln(16)/4) = 1.414 * sqrt(0.693) ~ 1.176
        assert score > 0.75

    def test_single_depth_search_selects_clean_winner(self) -> None:
        res: MCTSExecutionResult = self.engine.search("Implement sorting with binary boundary checks")
        assert res.total_branches_explored == 4
        assert res.passed_branches_count > 0
        assert res.winner_code
        assert res.best_score >= 0.5
        assert res.tree_depth == 1

        # Winner must be valid Python code
        parsed = ast.parse(res.winner_code)
        assert parsed is not None

    def test_multi_depth_mcts_search_expands_tree(self) -> None:
        multi_engine = MCTSSearchEngine(max_branches=3, max_depth=2, iterations=4)
        res: MCTSExecutionResult = multi_engine.search("Implement high performance cache", max_depth=2)
        assert res.total_branches_explored > 3  # Root branches (3) + expanded child nodes
        assert res.tree_depth >= 2
        assert res.winner_code
        assert res.best_score > 0.0

        parsed = ast.parse(res.winner_code)
        assert parsed is not None

    def test_refinement_expansion_and_backpropagation(self) -> None:
        root = MCTSNode(node_id="root", code_candidate="", depth=0)
        child = MCTSNode(
            node_id="child_1",
            code_candidate="""
from typing import Any, Dict
def solve(input_data: Any) -> Dict[str, Any]:
    return {'status': 'SUCCESS', 'result': input_data}
""",
            depth=1,
            parent=root,
        )
        root.children.append(child)

        refinements = self.engine._expand_refinements(child, "Cache lookup")
        assert len(refinements) == 2
        assert child.is_expanded is True

        # Test backpropagation
        self.engine._backpropagate(refinements[0], reward=0.8)
        assert child.visits == 1
        assert child.total_reward == 0.8
        assert root.visits == 1
        assert root.total_reward == 0.8
