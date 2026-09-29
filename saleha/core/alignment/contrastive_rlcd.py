"""Saleha Alignment: Reinforcement Learning from Contrastive Dialogue (RLCD).

Generates and verifies contrastive critique-revision pairs:
1. Generates an initial candidate solution (baseline).
2. Generates an adversarial/constitutional critique targeting security, types, and logic.
3. Generates a surgical revision addressing the critique.
4. Verifies physical reward margin (delta r = r_chosen - r_rejected) via RLHVR.
5. Rejects any pairs that do not physically satisfy the required margin or fail tests.
"""

from __future__ import annotations

import ast
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from saleha.core.alignment.verifiable_rewards import RLAIFAuditor, RLHVRVerifier
from saleha.core.dpo_dataset_engine import DPOPreferencePair


@dataclass
class RLCDPair:
    """A verified contrastive dialogue pair with measurable reward margin."""
    pair_id: str
    prompt: str
    critique: str
    chosen: str  # Revised high-reward code
    rejected: str  # Baseline or defective code
    chosen_reward: float
    rejected_reward: float
    margin_score: float
    verified: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dpo(self, language: str = "python", category: str = "contrastive_rlcd") -> DPOPreferencePair:
        return DPOPreferencePair(
            pair_id=self.pair_id,
            prompt=self.prompt,
            chosen=self.chosen,
            rejected=self.rejected,
            language=language,
            category=category,
            margin_score=self.margin_score,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "prompt": self.prompt,
            "critique": self.critique,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "chosen_reward": self.chosen_reward,
            "rejected_reward": self.rejected_reward,
            "margin_score": self.margin_score,
            "verified": self.verified,
            "metadata": self.metadata,
        }


class RLCDGenerator:
    """Generates and physically verifies contrastive dialogue pairs."""

    def __init__(
        self,
        verifier: Optional[RLHVRVerifier] = None,
        min_margin: float = 0.20,
    ) -> None:
        self.verifier = verifier or RLHVRVerifier()
        self.auditor = RLAIFAuditor()
        self.min_margin = min_margin

    def synthesize_pair_from_candidates(
        self,
        prompt: str,
        baseline_code: str,
        revised_code: str,
        critique: str,
        test_code: Optional[str] = None,
    ) -> Optional[RLCDPair]:
        """Evaluates baseline vs revised code using physical RLHVR and AI rubrics.
        
        Returns RLCDPair if revised code is strictly better than baseline
        by at least min_margin and chosen code passes tests.
        """
        revised_sig = self.verifier.verify_code(revised_code, test_code=test_code)
        baseline_sig = self.verifier.verify_code(baseline_code, test_code=test_code)

        # Invariant: Chosen code must be syntactically valid and pass tests if test_code is supplied
        if not revised_sig.ast_valid:
            return None

        if test_code and not revised_sig.passed_tests:
            return None

        margin = round(revised_sig.composite_score - baseline_sig.composite_score, 3)

        if margin < self.min_margin:
            return None

        pair_id = f"rlcd_{uuid.uuid4().hex[:8]}"
        return RLCDPair(
            pair_id=pair_id,
            prompt=prompt,
            critique=critique,
            chosen=revised_code,
            rejected=baseline_code,
            chosen_reward=revised_sig.composite_score,
            rejected_reward=baseline_sig.composite_score,
            margin_score=margin,
            verified=revised_sig.passed_tests if test_code else revised_sig.ast_valid,
            metadata={
                "chosen_hardware_reward": revised_sig.hardware_reward,
                "rejected_hardware_reward": baseline_sig.hardware_reward,
                "chosen_ai_reward": revised_sig.ai_feedback_reward,
                "rejected_ai_reward": baseline_sig.ai_feedback_reward,
                "execution_time_ms": revised_sig.execution_time_ms,
            },
        )

    def generate_contrastive_perturbations(
        self,
        clean_code: str,
        prompt: str,
        test_code: Optional[str] = None,
    ) -> List[RLCDPair]:
        """Systematically creates verifiable contrastive pairs by applying deterministic defect operators.
        
        Generates pairs where:
        - Chosen: Original verified clean code
        - Rejected: Perturbed code with specific physical defects (missing type hints, zero-division hazards, security issues)
        - Critique: Explanation of the introduced defect
        """
        pairs: List[RLCDPair] = []

        # Perturbation 1: Strip type annotations
        untyped_code = self._strip_type_annotations(clean_code)
        if untyped_code and untyped_code != clean_code:
            critique = "The code lacks type annotations and return type signatures, hindering static verification and readability."
            pair = self.synthesize_pair_from_candidates(
                prompt=prompt,
                baseline_code=untyped_code,
                revised_code=clean_code,
                critique=critique,
                test_code=test_code,
            )
            if pair:
                pairs.append(pair)

        # Perturbation 2: Inject zero-division hazard if arithmetic is present
        div_hazard_code = self._inject_division_hazard(clean_code)
        if div_hazard_code and div_hazard_code != clean_code:
            critique = "The code performs arithmetic division without verifying non-zero denominator bounds, risking ZeroDivisionError."
            pair = self.synthesize_pair_from_candidates(
                prompt=prompt,
                baseline_code=div_hazard_code,
                revised_code=clean_code,
                critique=critique,
                test_code=test_code,
            )
            if pair:
                pairs.append(pair)

        # Perturbation 3: Remove defensive assertions / guards
        unguarded_code = self._strip_assertions(clean_code)
        if unguarded_code and unguarded_code != clean_code:
            critique = "The code removes defensive preconditions and assertion invariants, allowing invalid state propagation."
            pair = self.synthesize_pair_from_candidates(
                prompt=prompt,
                baseline_code=unguarded_code,
                revised_code=clean_code,
                critique=critique,
                test_code=test_code,
            )
            if pair:
                pairs.append(pair)

        return pairs

    def _strip_type_annotations(self, code: str) -> Optional[str]:
        """AST-safe transformation stripping type annotations."""
        try:
            tree = ast.parse(code)
            class TypeStripper(ast.NodeTransformer):
                def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
                    self.generic_visit(node)
                    node.returns = None
                    for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                        arg.annotation = None
                    if node.args.vararg:
                        node.args.vararg.annotation = None
                    if node.args.kwarg:
                        node.args.kwarg.annotation = None
                    return node

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
                    return self.visit_FunctionDef(node)  # type: ignore

                def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
                    self.generic_visit(node)
                    if node.value is not None:
                        return ast.Assign(targets=[node.target], value=node.value)
                    return None

            new_tree = TypeStripper().visit(tree)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        except Exception:
            return None

    def _strip_assertions(self, code: str) -> Optional[str]:
        """AST-safe transformation removing assertions."""
        try:
            tree = ast.parse(code)
            class AssertionRemover(ast.NodeTransformer):
                def visit_Assert(self, node: ast.Assert) -> Any:
                    return None
            new_tree = AssertionRemover().visit(tree)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        except Exception:
            return None

    def _inject_division_hazard(self, code: str) -> Optional[str]:
        """AST transformation replacing safe division or inserting an unchecked division."""
        try:
            tree = ast.parse(code)
            # Find any division and remove defensive checks around it
            modified = False
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    # If checking for divisor != 0, replace test with True
                    if isinstance(node.test, ast.Compare):
                        modified = True
                        node.test = ast.Constant(value=True)
            if modified:
                return ast.unparse(tree)
            return None
        except Exception:
            return None
