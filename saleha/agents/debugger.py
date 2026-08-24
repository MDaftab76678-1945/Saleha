"""Debugger agent for diagnosing and repairing generated Python code."""

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from saleha.agents.base_agent import AgentResponse, BaseAgent
from saleha.core.self_healing import SelfHealingEngine


@dataclass
class DebugResult:
	success: bool
	diagnosis: str = ""
	fixed_code: str = ""
	error: str = ""
	model_used: str = ""


class DebuggerAgent(BaseAgent):
	"""Use the model to explain an error and produce a corrected code version."""

	def __init__(self, model: str = "auto", provider=None):
		super().__init__(role="Debugger", model=model, provider=provider)
		self.healing_engine = SelfHealingEngine()

	def debug_code(self, task: str, code: str, error_log: str) -> DebugResult:
		if not code.strip():
			return DebugResult(success=False, error="Code is empty.")
		if not error_log.strip():
			return DebugResult(success=False, error="Error log is empty.")

		healing = self.healing_engine.analyze_and_heal(error_log, task)
		prompt = f"""You are an expert Python debugger.

Task: {task}
Error log:
{error_log}

Existing code:
```python
{code}
```

Likely error type: {healing.error_type}
Likely root cause: {healing.root_cause_hint}

Return exactly this format:
DIAGNOSIS: one concise explanation
FIXED_CODE:
```python
the complete corrected code
```
"""
		response: AgentResponse = self.think(prompt)
		if not response.success:
			return DebugResult(success=False, error=response.error_message, model_used=response.model_used)

		diagnosis_match = re.search(r"^DIAGNOSIS:\s*(.+)$", response.content, re.MULTILINE | re.IGNORECASE)
		fixed_code = self._extract_code(response.content)
		diagnosis = diagnosis_match.group(1).strip() if diagnosis_match else ""
		if not fixed_code:
			return DebugResult(success=False, diagnosis=diagnosis, error="Model returned no corrected code.", model_used=response.model_used)

		return DebugResult(
			success=True,
			diagnosis=diagnosis,
			fixed_code=fixed_code,
			model_used=response.model_used,
		)

	@staticmethod
	def _extract_code(response: str) -> str:
		match = re.search(r"```(?:python)?\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
		return match.group(1).strip() if match else ""
