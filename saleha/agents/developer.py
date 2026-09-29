"""
Saleha Agents: Developer Agent

Polyglot fullstack software developer agent capable of implementing production features,
ORM data models, asynchronous API endpoints, and clean modular logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from saleha.agents.base_agent import AgentResponse, BaseAgent


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
        # Nothing is written to disk by this method, so files_created stays
        # empty: claiming a filename here previously read as "file created".
        # When the model returns no code, the fallback is an explicitly
        # labeled placeholder, not a passing implementation.
        if code_match:
            code = code_match.group(1).strip()
        elif resp.content and resp.content.strip():
            code = resp.content.strip()
        else:
            code = (f"# Offline placeholder for: {task}\n# No model produced code; "
                    "this stub does nothing.\n\ndef execute():\n    raise NotImplementedError("
                    "\"placeholder -- no implementation generated\")\n")

        deps = ["pydantic", "fastapi"] if language.lower() == "python" else ["typescript", "zod"]

        return DeveloperOutput(
            task=task,
            language=language,
            source_code=code,
            files_created=[],
            dependencies=deps,
            model_used=resp.model_used
        )
