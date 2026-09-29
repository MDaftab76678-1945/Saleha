"""
Saleha Core: Skill Base (New -- plugin-style extensibility)

The core agents (Planner, Coder, Tester, Reviewer) are hardcoded, so adding a
new capability would mean editing orchestrator.py. The "Skill" pattern avoids
that: a small specialised tool (for example a calculator skill that solves
simple math directly, without an LLM call) subclasses this base class in its
own file and is added to the registry -- no orchestrator change needed.

Design: every Skill answers two questions --
  1. can_handle(task) -- "is this task mine?"
  2. execute(task) -- "then do it"
The orchestrator (or any caller) first asks the registry whether some skill
can handle the task. If one can, it runs directly (no LLM call, fast and
deterministic). If none can, the normal Plan->Code->Test pipeline runs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SkillResult:
    success: bool
    output: str
    error: str = ""


class Skill(ABC):
    """Base class every skill inherits from."""

    name: str = "unnamed_skill"
    description: str = "No description provided."

    @abstractmethod
    def can_handle(self, task: str) -> bool:
        """Whether this task is within this skill's scope. Must be a fast check
        (no LLM call, only a keyword/pattern test)."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, task: str) -> SkillResult:
        """Handle the task and return the result."""
        raise NotImplementedError