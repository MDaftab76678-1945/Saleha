import unittest

from saleha.core.skill_base import Skill, SkillResult
from saleha.core.skill_registry import SkillRegistry


class ExampleSkill(Skill):
    name = "example"
    description = "test skill"

    def can_handle(self, task):
        return True

    def execute(self, task):
        return SkillResult(success=True, output=task)


class SkillRegistryTests(unittest.TestCase):
    def test_registering_same_skill_name_is_idempotent(self):
        registry = SkillRegistry()
        registry.register(ExampleSkill())
        registry.register(ExampleSkill())

        self.assertEqual([skill.name for skill in registry.list_skills()], ["example"])


if __name__ == "__main__":
    unittest.main()
