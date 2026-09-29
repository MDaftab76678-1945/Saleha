"""Saleha Core: Process Reward Model (PRM) & Monte Carlo Tree Search (MCTS) Engine.

Implements step-level process reward scoring and PUCT-guided tree search:
1. Decomposes code generation into verifiable logical steps (signatures, preconditions, core logic, return postconditions).
2. ProcessRewardModel (PRM) scores step quality [0.0, 1.0] and enforces early subtree pruning.
   The PRM is a static AST heuristic (typing, guards, returns, security audit),
   not a trained model; only the sandboxed terminal verification is ground truth.
3. PRMMCTSEngine uses PUCT (AlphaZero-style) with PRM priors:
   U(s, a) = Q(s, a) + c_puct * PRM(s, a) * sqrt(N(s)) / (1 + N(s, a))
4. Sandboxed terminal verification backpropagates RLHVR physical execution rewards.
"""

from __future__ import annotations

import ast
import copy
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from saleha.core.alignment.verifiable_rewards import RewardSignal, RLHVRVerifier
from saleha.sandbox.ast_security_verifier import ASTContractAuditor


@dataclass
class CodeStep:
    """A discrete logical step in code synthesis or refactoring."""
    step_index: int
    step_type: str  # "signature", "preconditions", "core_logic", "postconditions"
    code_fragment: str
    cumulative_code: str
    prm_score: float = 0.0  # [0.0, 1.0] from PRM
    is_valid: bool = True
    diagnostics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "step_type": self.step_type,
            "code_fragment": self.code_fragment,
            "cumulative_code": self.cumulative_code,
            "prm_score": self.prm_score,
            "is_valid": self.is_valid,
            "diagnostics": self.diagnostics,
        }


class ProcessRewardModel:
    """Heuristic step-level reward model: AST checks, no learned weights."""

    def __init__(self, prune_threshold: float = 0.30) -> None:
        self.prune_threshold = prune_threshold

    def evaluate_step(
        self,
        step_index: int,
        step_type: str,
        code_fragment: str,
        cumulative_code: str,
    ) -> CodeStep:
        """Evaluates an individual code step and assigns credit in [0.0, 1.0]."""
        diagnostics: List[str] = []

        # 1. AST Validity of Cumulative Code
        try:
            tree = ast.parse(cumulative_code)
        except SyntaxError as e:
            diagnostics.append(f"SyntaxError in step {step_index}: {e.msg}")
            return CodeStep(
                step_index=step_index,
                step_type=step_type,
                code_fragment=code_fragment,
                cumulative_code=cumulative_code,
                prm_score=0.0,
                is_valid=False,
                diagnostics=diagnostics,
            )

        # 2. Security audit of fragment & cumulative code
        is_safe, violations = ASTContractAuditor.audit(cumulative_code, require_assertions=False)
        if not is_safe:
            diagnostics.extend(violations)
            return CodeStep(
                step_index=step_index,
                step_type=step_type,
                code_fragment=code_fragment,
                cumulative_code=cumulative_code,
                prm_score=0.1,
                is_valid=False,
                diagnostics=diagnostics,
            )

        # 3. Step-Specific Heuristics & Invariants
        score = 0.5  # Base pass score

        if step_type == "signature":
            # Check typing of functions
            funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if funcs:
                fn = funcs[-1]
                has_typed_args = all(a.annotation is not None for a in fn.args.args if a.arg != "self")
                has_ret_type = fn.returns is not None
                has_docstring = ast.get_docstring(fn) is not None
                if has_typed_args:
                    score += 0.2
                if has_ret_type:
                    score += 0.2
                if has_docstring:
                    score += 0.1
            else:
                score = 0.3

        elif step_type == "preconditions":
            # Check for defensive assertions or if-guards
            has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(tree))
            has_guard = any(isinstance(n, ast.If) for n in ast.walk(tree))
            if has_assert or has_guard:
                score += 0.4
            else:
                diagnostics.append("Step lacks input validation or defensive preconditions.")
                score -= 0.1

        elif step_type == "core_logic":
            # Check for reasonable complexity and absence of unhandled operations
            branch_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.If, ast.While, ast.For)))
            if branch_count > 10:
                diagnostics.append("High cyclomatic complexity in core logic step.")
                score -= 0.2
            else:
                score += 0.3
            # Check for try/except or structured flow
            if any(isinstance(n, ast.Try) for n in ast.walk(tree)):
                score += 0.2

        elif step_type == "postconditions":
            # Check return statement presence
            returns = [n for n in ast.walk(tree) if isinstance(n, ast.Return)]
            if returns:
                score += 0.4
            else:
                diagnostics.append("Missing return statement in postcondition step.")
                score -= 0.2

        prm_score = round(max(0.0, min(1.0, score)), 3)
        is_valid = prm_score >= self.prune_threshold

        return CodeStep(
            step_index=step_index,
            step_type=step_type,
            code_fragment=code_fragment,
            cumulative_code=cumulative_code,
            prm_score=prm_score,
            is_valid=is_valid,
            diagnostics=diagnostics,
        )

    def decompose_code_to_steps(self, code: str) -> List[CodeStep]:
        """Decomposes an existing Python function into logical PRM steps."""
        steps: List[CodeStep] = []
        try:
            tree = ast.parse(code)
        except Exception:
            return [self.evaluate_step(0, "core_logic", code, code)]

        funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not funcs:
            return [self.evaluate_step(0, "core_logic", code, code)]

        fn = funcs[0]
        # Step 0: Imports + Signature + Docstring
        sig_lines = []
        for n in tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                sig_lines.append(ast.unparse(n))
        
        # Clone function with pass body to create signature step
        fn_sig = copy.deepcopy(fn)
        fn_sig.body = [ast.Pass()]
        sig_code = "\n".join(sig_lines + [ast.unparse(fn_sig)])
        steps.append(self.evaluate_step(0, "signature", sig_code, sig_code))

        # Partition body into preconditions, core logic, return
        precond_nodes = []
        core_nodes = []
        post_nodes = []

        for stmt in fn.body:
            if isinstance(stmt, (ast.Assert, ast.If)) and not core_nodes:
                precond_nodes.append(stmt)
            elif isinstance(stmt, ast.Return):
                post_nodes.append(stmt)
            else:
                core_nodes.append(stmt)

        # Cumulative step 1: Preconditions
        if precond_nodes:
            fn_pre = copy.deepcopy(fn)
            fn_pre.body = precond_nodes + [ast.Pass()]
            code_pre = "\n".join(sig_lines + [ast.unparse(fn_pre)])
            frag_pre = "\n".join(ast.unparse(s) for s in precond_nodes)
            steps.append(self.evaluate_step(1, "preconditions", frag_pre, code_pre))

        # Cumulative step 2: Core Logic
        if core_nodes:
            fn_core = copy.deepcopy(fn)
            fn_core.body = precond_nodes + core_nodes + ([ast.Pass()] if not post_nodes else [])
            code_core = "\n".join(sig_lines + [ast.unparse(fn_core)])
            frag_core = "\n".join(ast.unparse(s) for s in core_nodes)
            steps.append(self.evaluate_step(2, "core_logic", frag_core, code_core))

        # Cumulative step 3: Full Code (Postconditions)
        frag_post = "\n".join(ast.unparse(s) for s in post_nodes) if post_nodes else ""
        steps.append(self.evaluate_step(3, "postconditions", frag_post, code))

        return steps


@dataclass
class PRMNode:
    """A node in the PRM-guided Monte Carlo search tree."""
    node_id: str
    step: CodeStep
    parent: Optional[PRMNode] = None
    children: List[PRMNode] = field(default_factory=list)
    visits: int = 0
    total_reward: float = 0.0
    terminal_reward: Optional[RewardSignal] = None
    is_pruned: bool = False

    @property
    def q_value(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.total_reward / self.visits

    def puct_score(self, total_parent_visits: int, c_puct: float = 1.414) -> float:
        """PUCT score balancing exploitation, exploration, and step PRM prior."""
        if self.is_pruned:
            return -float("inf")
        exploitation = self.q_value
        exploration = c_puct * self.step.prm_score * (math.sqrt(total_parent_visits) / (1 + self.visits))
        return exploitation + exploration


@dataclass
class PRMMCTSResult:
    """Physical results of a PRM-guided MCTS search run."""
    task_prompt: str
    best_code: str
    best_composite_score: float
    hardware_reward: float
    ai_feedback_reward: float
    total_nodes_created: int
    branches_pruned: int
    search_duration_ms: float
    step_trace: List[CodeStep]
    passed_tests: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_prompt": self.task_prompt,
            "best_code": self.best_code,
            "best_composite_score": self.best_composite_score,
            "hardware_reward": self.hardware_reward,
            "ai_feedback_reward": self.ai_feedback_reward,
            "total_nodes_created": self.total_nodes_created,
            "branches_pruned": self.branches_pruned,
            "search_duration_ms": self.search_duration_ms,
            "step_trace": [s.to_dict() for s in self.step_trace],
            "passed_tests": self.passed_tests,
            "details": self.details,
        }


class PRMMCTSEngine:
    """Frontier Test-Time Compute Scaler: PRM-guided Monte Carlo Tree Search."""

    def __init__(
        self,
        c_puct: float = 1.414,
        max_depth: int = 4,
        prune_threshold: float = 0.30,
        verifier: Optional[RLHVRVerifier] = None,
    ) -> None:
        self.c_puct = c_puct
        self.max_depth = max_depth
        self.prm = ProcessRewardModel(prune_threshold=prune_threshold)
        self.verifier = verifier or RLHVRVerifier()

    def search(
        self,
        task_prompt: str,
        candidate_variations: List[str],
        test_code: Optional[str] = None,
        max_iterations: int = 10,
    ) -> PRMMCTSResult:
        """Executes PRM-guided MCTS over candidate code variants and step branches."""
        start_time = time.perf_counter()
        branches_pruned = 0
        total_nodes = 0

        # Root Node
        root_step = CodeStep(
            step_index=0,
            step_type="root",
            code_fragment="",
            cumulative_code="",
            prm_score=1.0,
            is_valid=True,
        )
        root = PRMNode(node_id="root", step=root_step)
        total_nodes += 1

        best_node: Optional[PRMNode] = None
        best_signal: Optional[RewardSignal] = None
        verified: Dict[str, RewardSignal] = {}

        # Build initial candidate branches decomposed into steps
        candidate_traces: List[List[CodeStep]] = []
        for code in candidate_variations:
            steps = self.prm.decompose_code_to_steps(code)
            candidate_traces.append(steps)

        # Populate tree with initial step paths
        for trace_idx, trace in enumerate(candidate_traces):
            current_parent = root
            for step in trace:
                node_id = f"node_{trace_idx}_{step.step_index}_{uuid.uuid4().hex[:4]}"
                child = PRMNode(
                    node_id=node_id,
                    step=step,
                    parent=current_parent,
                )
                total_nodes += 1
                if not step.is_valid:
                    child.is_pruned = True
                    branches_pruned += 1
                    current_parent.children.append(child)
                    break  # Prune remaining steps in this branch!

                current_parent.children.append(child)
                current_parent = child

        # Perform MCTS iterations
        for _ in range(max_iterations):
            # 1. Selection
            node = root
            while node.children and not node.is_pruned:
                # Filter out pruned children
                valid_children = [c for c in node.children if not c.is_pruned]
                if not valid_children:
                    break
                # Pick child with highest PUCT score
                node = max(valid_children, key=lambda c: c.puct_score(node.visits, self.c_puct))

            # 2. Evaluation / Simulation (Physical RLHVR at terminal or leaf)
            code_to_eval = node.step.cumulative_code
            if not code_to_eval:
                continue

            sig = verified.get(code_to_eval)
            if sig is None:
                sig = self.verifier.verify_code(code_to_eval, test_code=test_code)
                verified[code_to_eval] = sig
            node.terminal_reward = sig
            reward_val = sig.composite_score

            if best_signal is None or sig.composite_score > best_signal.composite_score:
                best_signal = sig
                best_node = node

            # 3. Backpropagation
            curr: Optional[PRMNode] = node
            while curr is not None:
                curr.visits += 1
                curr.total_reward += reward_val
                curr = curr.parent

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if best_node and best_signal:
            winner_code = best_node.step.cumulative_code
            # Reconstruct trace for winner
            winner_trace = []
            curr_trace_node: Optional[PRMNode] = best_node
            while curr_trace_node and curr_trace_node.step.step_type != "root":
                winner_trace.append(curr_trace_node.step)
                curr_trace_node = curr_trace_node.parent
            winner_trace.reverse()

            return PRMMCTSResult(
                task_prompt=task_prompt,
                best_code=winner_code,
                best_composite_score=best_signal.composite_score,
                hardware_reward=best_signal.hardware_reward,
                ai_feedback_reward=best_signal.ai_feedback_reward,
                total_nodes_created=total_nodes,
                branches_pruned=branches_pruned,
                search_duration_ms=round(elapsed_ms, 2),
                step_trace=winner_trace,
                passed_tests=best_signal.passed_tests,
                details={**best_signal.details, "sandbox_runs": len(verified)},
            )
        else:
            # Fallback if no valid node
            fallback_code = candidate_variations[0] if candidate_variations else ""
            return PRMMCTSResult(
                task_prompt=task_prompt,
                best_code=fallback_code,
                best_composite_score=-1.0,
                hardware_reward=-1.0,
                ai_feedback_reward=0.0,
                total_nodes_created=total_nodes,
                branches_pruned=branches_pruned,
                search_duration_ms=round(elapsed_ms, 2),
                step_trace=[],
                passed_tests=False,
                details={"error": "All branches pruned or failed verification"},
            )
