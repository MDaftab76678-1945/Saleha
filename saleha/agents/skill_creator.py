"""
Saleha Agents: New Skill Creator Agent

Writes a new AgentSkill -- an `execute_skill(context) -> dict` handler and
pytest tests for it -- runs the tests on the handler, and registers the
skill in the SkillCatalog only when they pass and `register=True` was
asked for. A failing or untested handler is returned as a draft, never
registered: an untested echo stub once filled the real catalog with skills
reporting "success" for work never done.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
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
    test_code: str = ""
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None      # True: the handler's tests ran and passed
    is_draft: bool = True                # True: no model answered; the handler raises NotImplementedError
    not_registered_because: str = ""


class NewSkillCreatorAgent(BaseAgent):
    """Autonomous Agent for Creating, Validating, and Registering New AgentSkills."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="SkillCreator", model=model)

    def create_and_register_skill(self, name: str, domain: str, description: str,
                                  keywords: Optional[List[str]] = None, category: str = "engineering",
                                  register: bool = False) -> CreatedSkillResult:
        """Handler + tests, run; registered only when they pass and `register=True`."""
        clean_id = "skill_" + re.sub(r"\W+", "_", name.lower()).strip("_")
        keys = keywords or [name.lower(), domain.lower(), "saleha", "automation"]
        prompt = (
            f"Write an AgentSkill named `{name}` (domain: {domain}).\nWhat it does: {description}\n"
            "Answer with exactly two fenced ```python blocks:\n"
            "1. solution.py: `def execute_skill(context: dict) -> dict` doing the real work with the standard "
            "library only, returning a dict with a `status` key ('ok' or 'error') and the results\n"
            "2. pytest tests: `from solution import execute_skill`, real inputs, plain asserts on the outputs, "
            "including an invalid input\nNo other text.")

        def build(content: str) -> Tuple[Tuple[str, str], List[ac.Check]]:
            blocks = [b for _i, b in ac.fenced_blocks(content)]
            handler = next((b for b in blocks if "def execute_skill" in b), "")
            tests = next((b for b in blocks if "def test" in b and b is not handler), "")
            checks = [ac.check_python(handler, "handler syntax")]
            if "def execute_skill" not in handler:
                checks.append(ac.Check("defines execute_skill", ac.FAIL, "no execute_skill function"))
            elif checks[0].status == ac.PASS:
                checks.append(ac.run_tests(handler, tests))
            return (handler, tests), checks

        files, checks, resp, _rounds = ac.produce(self, prompt, build)
        is_draft = files is None or "def execute_skill" not in files[0]
        if is_draft:
            checks = ac.fallback_note(checks, files is not None)
            handler = (f"# AgentSkill DRAFT (no model answered): {name} ({clean_id})\n"
                       "def execute_skill(context: dict) -> dict:\n"
                       f"    \"\"\"{description}\"\"\"\n"
                       "    raise NotImplementedError(\"skill draft -- implement and test before use\")\n")
            tests = ""
        else:
            handler, tests = files
        verified = None if is_draft else ac.verdict(checks)

        registered, why_not = False, ""
        if register and verified:
            skill_catalog.register_skill(AgentSkill(
                name=name, domain=domain, description=description, trigger_keywords=keys,
                input_schema={"type": "object", "properties": {"params": {"type": "object"}}},
                output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
                tags=[domain, category]))
            registered = True
        elif register:
            why_not = ("no model wrote a handler" if is_draft
                       else "its tests did not pass: " + "; ".join(c.detail for c in checks if c.status != ac.PASS)[:300])

        md_doc = (f"# Skill: {name}\n\n## Domain\n`{domain}` ({category})\n\n## Description\n{description}\n\n"
                  f"## Keywords\n{', '.join(f'`{k}`' for k in keys)}\n\n"
                  f"## Status\n{'tests passed' if verified else 'draft -- not verified'}\n\n"
                  f"## Handler\n```python\n{handler}\n```\n")
        return CreatedSkillResult(
            skill_id=clean_id, name=name, domain=domain, registered_in_catalog=registered,
            python_handler_snippet=handler, markdown_doc=md_doc, keywords=keys, test_code=tests,
            checks=ac.as_dicts(checks), verified=verified, is_draft=is_draft, not_registered_because=why_not)
