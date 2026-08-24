"""
Saleha Core: Skill Base (New -- plugin-style extensibility)

Abhi Saleha ke agents (Planner, Coder, Tester, Reviewer) sab hardcoded hain
-- naya capability add karna matlab orchestrator.py khud chhedna. Ye "Skill"
pattern isse alag banata hai: koi bhi naya chhota specialized tool (jaise
"calculator skill" jo simple math ko bina LLM call kiye seedha solve kare)
is base class se inherit karke naya file bana sakta hai, aur registry me
register ho jaata hai -- orchestrator ko chhedne ki zaroorat nahi.

Design: har Skill do cheezein batata hai --
  1. can_handle(task) -- "kya ye task mera kaam hai?"
  2. execute(task) -- "to yahi karo"
Orchestrator (ya koi bhi caller) pehle registry se poochta hai "koi skill
is task ko handle kar sakta hai?" -- agar haan, seedha wahi chalta hai
(LLM call bina, fast aur reliable). Agar nahi, normal Plan->Code->Test
pipeline chalta hai jaisa abhi hai.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SkillResult:
    success: bool
    output: str
    error: str = ""


class Skill(ABC):
    """Har naya skill isse inherit karega."""

    name: str = "unnamed_skill"
    description: str = "No description provided."

    @abstractmethod
    def can_handle(self, task: str) -> bool:
        """Ye task is skill ke scope me aata hai? Fast check hona chahiye
        (koi LLM call nahi, sirf keyword/pattern check)."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, task: str) -> SkillResult:
        """Task ko handle karo aur result do."""
        raise NotImplementedError