"""
Saleha Core: Auto-Curriculum & Prompt Self-Optimization Engine (PromptOptimizer)

Implements continuous self-refinement for multi-agent system prompts (DSPy/OPRO style):
1. Error Log Ingestion: Parses syntax errors, test failures, and hallucinations.
2. Directive Synthesis: Generates targeted behavioral constraints to mitigate recurring faults.
3. System Prompt Mutation: Optimizes base role prompts without retraining the underlying model.
4. Persistent Prompt Profiles in ~/.saleha/optimized_prompts.json.
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass
class PromptOptimizationRecord:
    """Represents an optimization iteration for a specific agent role."""
    role_name: str
    original_prompt: str
    optimized_prompt: str
    added_directives: List[str]
    iteration: int
    timestamp: float = field(default_factory=time.time)


class PromptOptimizer:
    """Auto-curriculum self-refining prompt optimizer."""

    DEFAULT_STORE = os.path.expanduser("~/.saleha/optimized_prompts.json")

    DIRECTIVE_MAP = {
        "IndexError": "Always check container lengths and index boundaries before accessing elements.",
        "ZeroDivisionError": "Always guard division operations with non-zero divisor assertions.",
        "TypeError": "Strictly validate all parameter types with isinstance checks before operations.",
        "KeyError": "Use dict.get() with fallback defaults rather than direct key subscripting.",
        "AttributeError": "Verify object interface attributes exist prior to invoking member methods.",
        "ModuleNotFoundError": "Only use Python standard library modules unless dependencies are declared in pyproject.toml.",
    }

    def __init__(self, store_path: Optional[str] = None):
        """Initializes the prompt self-optimizer."""
        self.store_path = store_path or self.DEFAULT_STORE
        self.history: List[PromptOptimizationRecord] = []
        self._load()

    def optimize_prompt(
        self,
        role_name: str,
        current_prompt: str,
        recent_errors: List[str],
    ) -> PromptOptimizationRecord:
        """Analyzes error patterns and synthesizes an improved system prompt with safety directives."""
        new_directives: List[str] = []

        for err in recent_errors:
            for err_type, directive in self.DIRECTIVE_MAP.items():
                if err_type.lower() in err.lower() and directive not in new_directives:
                    new_directives.append(directive)

        if not new_directives:
            new_directives.append("Ensure complete test assertion coverage and comprehensive docstrings.")

        directives_str = "\n".join(f"- [Auto-Optimized Guideline] {d}" for d in new_directives)
        optimized = f"{current_prompt.strip()}\n\n### Self-Refined Behavioral Directives:\n{directives_str}\n"

        record = PromptOptimizationRecord(
            role_name=role_name,
            original_prompt=current_prompt,
            optimized_prompt=optimized,
            added_directives=new_directives,
            iteration=len(self.history) + 1,
        )
        self.history.append(record)
        self.save()
        return record

    def save(self):
        """Persists optimized prompt records to disk."""
        try:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self.history], f, indent=2)
        except (OSError, IOError):
            pass  # noqa

    def _load(self):
        """Loads historical prompt optimization runs."""
        if not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.history = [PromptOptimizationRecord(**d) for d in data]
        except (OSError, IOError, json.JSONDecodeError):
            pass  # noqa


prompt_optimizer = PromptOptimizer()


if __name__ == "__main__":
    _opt = PromptOptimizer()
    _rec = _opt.optimize_prompt("CoderAgent", "You are an expert coder.", ["ZeroDivisionError in line 4"])
