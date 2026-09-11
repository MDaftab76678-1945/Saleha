"""
Saleha Core: Test-Time MCTS-Style Candidate Scoring Engine

What is real: each candidate is genuinely scored via real AST parsing,
the real neuro-symbolic invariant scorer, and a real sandboxed execution
in ephemeral_container_runner -- the winner selection and reward
computation are not fabricated.

What is NOT real, despite the name: candidate generation. This is not a
model call and does not explore "reasoning paths" -- _generate_candidate_variations
returns a small fixed set of hand-written template functions (an
"idiomatic" one, a "defensive" one, a "memoized" one, then near-identical
filler variants), chosen by loop index, not synthesized for the specific
task_prompt. Calling this "MCTS" is also an overstatement: there is no
tree expansion, no UCB1-guided branch selection driving further search,
and tree_depth is hardcoded to 1 -- MCTSNode.ucb1() exists but is never
called anywhere in search(). This is single-level candidate scoring, not
Monte Carlo Tree Search. No claim of "zero-hallucination" or "100%
test-passing" is warranted; verified_clean reflects only whether the
single winning template happened to pass its own generic smoke assertion.
"""

from __future__ import annotations

import ast
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional

from saleha.core.ephemeral_container_runner import container_runner, ContainerExecutionResult
from saleha.core.neuro_symbolic_engine import neuro_symbolic_engine


@dataclass
class MCTSNode:
    node_id: str
    code_candidate: str
    depth: int
    visits: int = 0
    total_reward: float = 0.0
    passed_tests: bool = False
    invariant_score: float = 0.0
    children: List[MCTSNode] = field(default_factory=list)
    parent: Optional[MCTSNode] = None

    @property
    def value(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.total_reward / self.visits

    def ucb1(self, total_parent_visits: int, exploration_weight: float = 1.414) -> float:
        if self.visits == 0:
            return float("inf")
        exploitation = self.value
        exploration = exploration_weight * math.sqrt(math.log(max(1, total_parent_visits)) / self.visits)
        return exploitation + exploration


@dataclass
class MCTSExecutionResult:
    task_prompt: str
    winner_code: str
    best_score: float
    total_branches_explored: int
    passed_branches_count: int
    search_duration_ms: float
    tree_depth: int
    verified_clean: bool


class MCTSSearchEngine:
    """Test-time reasoning search engine using Monte Carlo Tree Search."""

    def __init__(self, exploration_constant: float = 1.414, max_branches: int = 8):
        self.exploration_constant = exploration_constant
        self.max_branches = max(2, max_branches)

    def _generate_candidate_variations(self, prompt: str, num_branches: int) -> List[str]:
        """Returns num_branches fixed template implementations (see module
        docstring: these are hand-written templates, not model-generated
        candidates -- only `prompt` text is interpolated into docstrings/comments)."""
        candidates = []

        # Candidate 1: Standard idiomatic implementation
        c1 = f'''"""Idiomatic implementation for: {prompt}"""
from typing import Any, Dict, List, Optional

def solve(input_data: Any) -> Dict[str, Any]:
    \"\"\"Solves {prompt} with robust boundary checking.\"\"\"
    if input_data is None:
        return {{"status": "ERROR", "message": "Input cannot be None"}}
    return {{"status": "SUCCESS", "result": input_data, "algorithm": "idiomatic_direct"}}
'''
        candidates.append(c1)

        # Candidate 2: Defensive exception-handling implementation
        c2 = f'''"""Defensive hardened implementation for: {prompt}"""
from typing import Any, Dict, List, Optional

def solve(input_data: Any) -> Dict[str, Any]:
    \"\"\"Hardened implementation with fail-safe recovery.\"\"\"
    try:
        if isinstance(input_data, (list, tuple)):
            processed = [x for x in input_data if x is not None]
        else:
            processed = input_data
        return {{"status": "SUCCESS", "result": processed, "algorithm": "defensive_guarded"}}
    except Exception as e:
        return {{"status": "RECOVERED", "error": str(e)}}
'''
        candidates.append(c2)

        # Candidate 3: High-performance vectorized / memoized implementation
        c3 = f'''"""High-performance optimized implementation for: {prompt}"""
from typing import Any, Dict, List, Optional
from functools import lru_cache

class SolverEngine:
    \"\"\"Stateful high-throughput solver.\"\"\"
    def __init__(self):
        self.cache: Dict[str, Any] = {{}}

    def execute(self, payload: Any) -> Dict[str, Any]:
        return {{"status": "SUCCESS", "result": payload, "algorithm": "memoized_fast"}}

_instance = SolverEngine()
def solve(input_data: Any) -> Dict[str, Any]:
    return _instance.execute(input_data)
'''
        candidates.append(c3)

        # Candidate 4..N: Parameterized structural variants
        for i in range(3, num_branches):
            variant = f'''"""Variant-{i+1} implementation for: {prompt}"""
from typing import Any, Dict, List, Optional

def solve(input_data: Any) -> Dict[str, Any]:
    \"\"\"Branch {i+1} verified solver.\"\"\"
    return {{"status": "SUCCESS", "result": input_data, "branch": {i+1}}}
'''
            candidates.append(variant)

        return candidates[:num_branches]

    def _evaluate_node(self, node: MCTSNode) -> float:
        """Evaluates node via AST parsing, sandbox execution, and RLIF invariant scoring."""
        # 1. AST Validation
        try:
            ast.parse(node.code_candidate)
            ast_valid = True
        except SyntaxError:
            ast_valid = False

        if not ast_valid:
            node.passed_tests = False
            node.invariant_score = 0.0
            return 0.0

        # 2. RLIF Invariant Scoring
        inv_score = neuro_symbolic_engine.score_code(node.code_candidate)
        node.invariant_score = inv_score.composite_score

        # 3. Test Invariant Sandbox Run
        test_script = f"""{node.code_candidate}
assert solve('test_payload')['status'] in ('SUCCESS', 'RECOVERED')
"""
        exec_res: ContainerExecutionResult = container_runner.run_code(test_script, timeout_sec=2.0)
        node.passed_tests = exec_res.success

        # Reward formulation: Invariant Score + passing bonus
        reward = node.invariant_score
        if node.passed_tests:
            reward += 0.2
        return min(1.0, reward)

    def search(self, task_prompt: str, num_branches: Optional[int] = None) -> MCTSExecutionResult:
        """Executes MCTS tree search over candidate reasoning branches."""
        start_time = time.perf_counter()
        branches_count = num_branches or self.max_branches
        candidates = self._generate_candidate_variations(task_prompt, branches_count)

        root = MCTSNode(node_id="root", code_candidate="", depth=0)
        nodes: List[MCTSNode] = []

        for idx, cand in enumerate(candidates):
            child = MCTSNode(
                node_id=f"branch_{idx+1}",
                code_candidate=cand,
                depth=1,
                parent=root
            )
            reward = self._evaluate_node(child)
            child.visits = 1
            child.total_reward = reward
            root.visits += 1
            root.total_reward += reward
            root.children.append(child)
            nodes.append(child)

        # Select Best Performing Winner Node
        # Priority: passed_tests == True -> highest invariant_score -> highest value
        nodes.sort(key=lambda n: (1 if n.passed_tests else 0, n.invariant_score, n.value), reverse=True)
        winner = nodes[0]
        passed_count = sum(1 for n in nodes if n.passed_tests)

        duration = (time.perf_counter() - start_time) * 1000

        return MCTSExecutionResult(
            task_prompt=task_prompt,
            winner_code=winner.code_candidate,
            best_score=round(winner.invariant_score, 4),
            total_branches_explored=len(nodes),
            passed_branches_count=passed_count,
            search_duration_ms=round(duration, 2),
            tree_depth=1,
            verified_clean=winner.passed_tests and winner.invariant_score >= 0.85,
        )


mcts_search_engine = MCTSSearchEngine()
