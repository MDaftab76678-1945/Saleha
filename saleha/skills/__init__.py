"""
Saleha Skills: Built-in executable skills, Multi-Agent persona definitions, and AgentSkills Catalog.
"""

from saleha.core.skills.skill_catalog import AgentSkillMetadata, SkillCatalog, skill_catalog
from saleha.core.skills.skill_registry import SkillRegistry, registry
from saleha.skills.calculator_skill import CalculatorSkill
from saleha.skills.datetime_skill import DateTimeSkill
from saleha.skills.git_skill import GitSkill
from saleha.skills.unit_converter_skill import UnitConverterSkill

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
