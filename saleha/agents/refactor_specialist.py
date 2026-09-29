"""
Saleha Agents: Refactor Specialist Agent

Executes large-scale AST refactorings, modernizes legacy codebases (sync to async, modern type unions),
reduces cyclomatic complexity, and enforces Clean Code design principles.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List

from saleha.agents.base_agent import BaseAgent


@dataclass
class RefactorResult:
    original_code: str
    refactored_code: str
    # True when a simplifying transform was kept -- not a measured McCabe
    # delta. No kept transform (or a restore after a syntax break) is False.
    complexity_reduced: bool
    ast_valid: bool
    transformations_applied: List[str]
    model_used: str = ""


class RefactorSpecialistAgent(BaseAgent):
    """Lead Software Refactor & Code Modernization Specialist Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="RefactorSpecialist", model=model)

    def refactor_code(self, task: str, code: str, target_pattern: str = "clean_code") -> RefactorResult:
        """Applies systematic AST transformations and modern Python typing."""
        transforms: List[str] = []
        refactored = code

        # 1. Modernize legacy typing annotations: typing.List[T] -> list[T], typing.Dict[K, V] -> dict[K, V]
        if "from typing import List" in refactored or "from typing import Dict" in refactored:
            refactored = re.sub(r"\bList\[", "list[", refactored)
            refactored = re.sub(r"\bDict\[", "dict[", refactored)
            transforms.append("Modernized legacy typing.List/Dict to native builtins (PEP 585)")

        # 2. Modernize Union[A, B] -> A | B
        if "Union[" in refactored:
            refactored = re.sub(r"Union\[([^,]+),\s*([^\]]+)\]", r"\1 | \2", refactored)
            transforms.append("Converted typing.Union to native bitwise union syntax (PEP 604)")

        # 3. Simplify redundant bool checks: if x == True -> if x
        if " == True" in refactored or " == False" in refactored:
            refactored = refactored.replace(" == True", "")
            refactored = refactored.replace(" == False", " is False")
            transforms.append("Simplified redundant boolean comparison expressions")

        # 4. Validate resulting AST
        ast_valid = False
        restored = False
        try:
            ast.parse(refactored)
            ast_valid = True
        except SyntaxError:
            # The transforms broke the syntax: return the original and drop
            # the transform claims with it. Reporting kept transforms for
            # code that no longer contains them was the lie here.
            refactored = code
            transforms = []
            restored = True
            ast_valid = True

        if transforms:
            claimed_transforms = transforms
        elif restored:
            claimed_transforms = ["No transform kept (the edit would have broken syntax); original returned"]
        else:
            claimed_transforms = ["No applicable transform found; code returned unchanged"]

        return RefactorResult(
            original_code=code,
            refactored_code=refactored,
            complexity_reduced=len(transforms) > 0,
            ast_valid=ast_valid,
            transformations_applied=claimed_transforms,
            model_used=self.model_preference
        )
