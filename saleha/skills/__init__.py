"""
Saleha Skills: Built-in executable skills, Multi-Agent persona definitions, and AgentSkills Catalog.
"""

from saleha.skills.calculator_skill import CalculatorSkill
from saleha.skills.datetime_skill import DateTimeSkill
from saleha.skills.git_skill import GitSkill
from saleha.skills.unit_converter_skill import UnitConverterSkill
from saleha.core.skill_catalog import skill_catalog, SkillCatalog, AgentSkillMetadata
from saleha.core.skill_registry import registry, SkillRegistry

__all__ = [
    "CalculatorSkill",
    "DateTimeSkill",
    "GitSkill",
    "UnitConverterSkill",
    "skill_catalog",
    "SkillCatalog",
    "AgentSkillMetadata",
    "registry",
    "SkillRegistry",
]
