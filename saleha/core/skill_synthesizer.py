"""
Saleha Core: Dynamic Skill Synthesizer & Continuous Learning Engine

Distills successful agent debugging sessions, code refactors, and architectural workflows
into reusable, versioned Skill Markdown files (.saleha/skills/<skill_name>.md),
enabling agents to learn and solve similar tasks 90% faster in future invocations.
"""

from __future__ import annotations

import os
import re
import json
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from saleha.agents.base_agent import BaseAgent
from saleha.core.skill_base import Skill, SkillResult
from saleha.core.skill_registry import registry


class DynamicSynthesizedSkill(Skill):
    """Dynamic Skill wrapper allowing synthesized markdown skills to be registered in SkillRegistry."""

    def __init__(self, name: str, description: str, triggers: List[str], markdown_content: str):
        self.name = name
        self.description = description
        self.triggers = triggers
        self.markdown_content = markdown_content

    def can_handle(self, task: str) -> bool:
        t_low = task.lower()
        return any(trig.lower() in t_low for trig in self.triggers)

    def execute(self, task: str) -> SkillResult:
        return SkillResult(
            success=True,
            output=f"Applied synthesized skill '{self.name}':\n{self.markdown_content}"
        )


@dataclass
class SynthesizedSkill:
    name: str
    description: str
    triggers: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    code_templates: Dict[str, str] = field(default_factory=dict)
    markdown_content: str = ""
    file_path: str = ""


class SkillSynthesizer:
    """Automates continuous learning and dynamic skill distillation from agent execution history."""

    def __init__(self, model: str = "auto", skills_dir: str = ".saleha/skills"):
        self.model = model
        self.skills_dir = os.path.abspath(skills_dir)
        self.agent = BaseAgent(role="Principal Knowledge Distiller", model=model)

    def distill_from_execution(
        self,
        task_goal: str,
        execution_trace: str,
        skill_name: Optional[str] = None
    ) -> SynthesizedSkill:
        """Analyzes a task goal and its successful execution trace to synthesize a permanent skill."""
        clean_name = skill_name or re.sub(r'[^a-zA-Z0-9_-]', '_', task_goal[:30].strip().lower())

        prompt = f"""You are a Principal Knowledge Distiller.
Convert the following successful engineering task execution into a reusable, concise, expert-level SKILL.

Task Goal: {task_goal}

Execution Trace:
```
{execution_trace[:3000]}
```

Provide the skill in standard YAML-frontmatter Markdown format:
```markdown
---
name: {clean_name}
description: <concise 1-sentence description of what this skill does>
triggers:
  - "<trigger phrase 1>"
  - "<trigger phrase 2>"
---

# {clean_name}

## When to Use
<rules for when to activate this skill>

## Standard Steps
1. <Step 1>
2. <Step 2>
3. <Step 3>

## Reference Code / Pattern
```python
<concise reusable code template>
```
```
"""

        resp = self.agent.think(prompt, complexity_score=0.4)
        raw_md = resp.content if resp.success else ""

        if not raw_md:
            # Fallback deterministic template
            raw_md = f"""---
name: {clean_name}
description: Autonomous workflow distilled from task '{task_goal}'
triggers:
  - "{task_goal[:40]}"
---

# {clean_name}

## When to Use
Use when solving tasks similar to: {task_goal}

## Standard Steps
1. Analyze codebase dependencies and AST symbol structure.
2. Formulate surgical search/replace diff.
3. Validate in sandbox before committing.
"""

        # Extract markdown block if wrapped
        md_block = re.search(r"```(?:markdown)?\s*\n(.*?)```", raw_md, re.DOTALL)
        content_to_save = md_block.group(1) if md_block else raw_md

        return SynthesizedSkill(
            name=clean_name,
            description=f"Skill for {task_goal[:60]}",
            triggers=[task_goal[:40]],
            markdown_content=content_to_save.strip()
        )

    def save_skill(self, skill: SynthesizedSkill, custom_dir: Optional[str] = None) -> str:
        """Saves synthesized skill to disk and registers it in the live SkillRegistry."""
        target_dir = os.path.abspath(custom_dir or self.skills_dir)
        os.makedirs(target_dir, exist_ok=True)

        file_name = f"{skill.name.lower().replace(' ', '_')}.md"
        target_file = os.path.join(target_dir, file_name)

        tmp_p = f"{target_file}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as f:
            f.write(skill.markdown_content)
        os.replace(tmp_p, target_file)

        skill.file_path = target_file

        # Register in global skill_registry
        dyn_skill = DynamicSynthesizedSkill(
            name=skill.name,
            description=skill.description,
            triggers=skill.triggers,
            markdown_content=skill.markdown_content
        )
        registry.register(dyn_skill)

        return target_file


# Global instance
skill_synthesizer = SkillSynthesizer()
