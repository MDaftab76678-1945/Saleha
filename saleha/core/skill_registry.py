"""
Saleha Core: Skill Registry (New -- plugin-style extensibility)

Skills yahan register hote hain, aur koi bhi caller (orchestrator, CLI)
`find_skill(task)` bula ke poochh sakta hai "iske liye koi skill hai?".

Naya skill add karna:
    from core.skill_base import Skill, SkillResult
    from core.skill_registry import registry

    class MySkill(Skill):
        name = "my_skill"
        description = "..."
        def can_handle(self, task): ...
        def execute(self, task): ...

    registry.register(MySkill())

Bas itna -- orchestrator.py ko chhedne ki zaroorat nahi.
"""

from typing import List, Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from saleha.core.skill_base import Skill


class SkillRegistry:
    def __init__(self):
        self._skills: List[Skill] = []

    def register(self, skill: Skill):
        if any(existing.name == skill.name for existing in self._skills):
            return
        self._skills.append(skill)

    def list_skills(self) -> List[Skill]:
        return list(self._skills)

    def find_skill(self, task: str) -> Optional[Skill]:
        """Pehla skill jo is task ko handle kar sakta hai, return karta hai.
        Koi na mile to None (caller normal pipeline pe fallback kare)."""
        for skill in self._skills:
            try:
                if skill.can_handle(task):
                    return skill
            except (TypeError, ValueError, AttributeError):
                # Ek skill ka can_handle crash ho jaye to poora registry
                # na tooте -- bas is skill ko skip karo
                continue
        return None


# Global registry -- poore Saleha me yahi ek instance use hoga
registry = SkillRegistry()


def load_builtin_skills():
    """Saleha ke saath aane wale built-in skills load karta hai. Naye
    built-in skill add karne ke liye bas import + register yahan jodo."""
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from saleha.skills.calculator_skill import CalculatorSkill
    from saleha.skills.unit_converter_skill import UnitConverterSkill
    from saleha.skills.datetime_skill import DateTimeSkill
    from saleha.skills.git_skill import GitSkill
    registry.register(CalculatorSkill())
    registry.register(UnitConverterSkill())
    registry.register(DateTimeSkill())
    registry.register(GitSkill())


if __name__ == "__main__":
    load_builtin_skills()
    print("Registered skills:")
    for s in registry.list_skills():
        print(f"  - {s.name}: {s.description}")

    test_task = "What is 12 * 8?"
    found = registry.find_skill(test_task)
    print(f"\nTask: '{test_task}'")
    print(f"Matched skill: {found.name if found else 'None (normal pipeline)'}")
    if found:
        result = found.execute(test_task)
        print(f"Result: {result.output}")