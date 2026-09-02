"""
Saleha Agents: Developer Agent

Polyglot fullstack software developer agent capable of implementing production features,
ORM data models, asynchronous API endpoints, and clean modular logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.agents.base_agent import BaseAgent, AgentResponse


@dataclass
class DeveloperOutput:
    task: str
    language: str
    source_code: str
    files_created: List[str]
    dependencies: List[str]
    model_used: str = ""


class DeveloperAgent(BaseAgent):
    """Principal Polyglot Software Developer Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Developer", model=model)

    def develop_feature(
        self,
        task: str,
        language: str = "python",
        existing_context: Optional[str] = None
    ) -> DeveloperOutput:
        """Develops end-to-end clean source code implementation for the specified task."""
        ctx = f"\nContext:\n{existing_context}" if existing_context else ""
        prompt = f"""You are a Principal Software Developer. Write clean, production-grade {language} code for:
Task: {task}
{ctx}
Requirements:
1. Include modern type annotations.
2. Include error handling and docstrings.
3. Keep code modular and testable.
"""
        resp: AgentResponse = self.think(prompt)

        code_match = re.search(r"```(?:\w+)?\n([\s\S]*?)```", resp.content or "")
        code = code_match.group(1).strip() if code_match else (resp.content or f"# Feature: {task}\n\ndef execute():\n    return 'success'\n")

        filename = f"{task.lower().replace(' ', '_')[:25]}.py" if language.lower() == "python" else f"{task.lower().replace(' ', '_')[:25]}.ts"

        deps = ["pydantic", "fastapi"] if language.lower() == "python" else ["typescript", "zod"]

        return DeveloperOutput(
            task=task,
            language=language,
            source_code=code,
            files_created=[filename],
            dependencies=deps,
            model_used=resp.model_used
        )
