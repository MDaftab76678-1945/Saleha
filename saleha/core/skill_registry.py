"""
Saleha Core: Skill Registry (New -- plugin-style extensibility)

Skills are registered here, and any caller (orchestrator, CLI) can call
`find_skill(task)` to ask "is there a skill for this?".

Adding a skill:
    from saleha.core.skill_base import Skill, SkillResult
    from saleha.core.skill_registry import registry

    class MySkill(Skill):
        name = "my_skill"
        description = "..."
        def can_handle(self, task): ...
        def execute(self, task): ...

    registry.register(MySkill())

That is all -- orchestrator.py does not need to change.
"""

from typing import List, Optional

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
        """Returns the first skill that can handle this task, or None if no
        skill can (the caller then falls back to the normal pipeline)."""
        for skill in self._skills:
            try:
                if skill.can_handle(task):
                    return skill
            except (TypeError, ValueError, AttributeError):
                # One skill's can_handle crashing must not break the whole
                # registry -- skip that skill.
                continue
        return None


# Global registry -- the single instance used across Saleha
registry = SkillRegistry()


def load_builtin_skills():
    """Loads the built-in skills that ship with Saleha. To add another
    built-in skill, import it and register it here."""
    from saleha.skills.calculator_skill import CalculatorSkill
    from saleha.skills.datetime_skill import DateTimeSkill
    from saleha.skills.git_skill import GitSkill
    from saleha.skills.unit_converter_skill import UnitConverterSkill
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