"""
Saleha Agents: New Skill Creator Agent

Autonomously synthesizes, tests, registers, and catalogs new AgentSkills into
Saleha's 1,000+ SkillCatalog and agent profile registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from saleha.agents.base_agent import BaseAgent
from saleha.core.skills.skill_catalog import AgentSkill, skill_catalog


@dataclass
class CreatedSkillResult:
    skill_id: str
    name: str
    domain: str
    registered_in_catalog: bool
    python_handler_snippet: str
    markdown_doc: str
    keywords: List[str]


class NewSkillCreatorAgent(BaseAgent):
    """Autonomous Agent for Creating, Validating, and Registering New AgentSkills."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="SkillCreator", model=model)

    def create_and_register_skill(
        self,
        name: str,
        domain: str,
        description: str,
        keywords: Optional[List[str]] = None,
        category: str = "engineering",
        register: bool = False,
    ) -> CreatedSkillResult:
        """Builds a skill draft. Nothing is registered unless
        ``register=True``: the generated handler is an untested echo stub,
        and auto-registering it previously polluted the real catalog with
        entries reporting ``"status": "success"`` for work never done."""
        clean_id = f"skill_{name.lower().replace(' ', '_').replace('-', '_')}"
        keys = keywords or [name.lower(), domain.lower(), "saleha", "automation"]

        # 1. Python Execution Handler (untested draft -- review before registering)
        py_handler = f"""# ==============================================================================
# AgentSkill DRAFT (untested): {name} ({clean_id})
# Domain: {domain} | Category: {category}
# This echo stub always reports success. Implement the real logic and test
# it before registering this skill anywhere.
# ==============================================================================

def execute_skill(context: dict) -> dict:
    \"\"\"{description}\"\"\"
    raise NotImplementedError("skill draft -- implement and test before use")
"""

        # 2. Markdown Skill Doc
        md_doc = f"""# Skill: {name}

## Domain
`{domain}` ({category})

## Description
{description}

## Keywords
{', '.join(f'`{k}`' for k in keys)}

## Handler Implementation
```python
{py_handler}
```
"""

        # 3. Register in SkillCatalog -- only when explicitly asked, and
        # never for an untested draft.
        registered = False
        if register:
            new_skill = AgentSkill(
                name=name,
                domain=domain,
                description=description,
                trigger_keywords=keys,
                input_schema={"type": "object", "properties": {"params": {"type": "object"}}},
                output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
                tags=[domain, category]
            )
            skill_catalog.register_skill(new_skill)
            registered = True

        return CreatedSkillResult(
            skill_id=clean_id,
            name=name,
            domain=domain,
            registered_in_catalog=registered,
            python_handler_snippet=py_handler,
            markdown_doc=md_doc,
            keywords=keys
        )
