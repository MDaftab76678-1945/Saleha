"""Debugger agent for diagnosing and repairing generated Python code.

The model explains the error and writes corrected code; the correction is
then checked: it must compile, and when tests are given they are run on it
-- a fix that still fails is shown to the model once with the failure.
`verified` is True only when the given tests pass on the fixed code.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class DebugResult:
    success: bool
    diagnosis: str = ""
    fixed_code: str = ""
    error: str = ""
    model_used: str = ""
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None      # True: the given tests pass on fixed_code


class DebuggerAgent(BaseAgent):
    """Use the model to explain an error and produce a corrected code version."""

    def __init__(self, model: str = "auto", provider=None):
        super().__init__(role="Debugger", model=model, provider=provider)
        # Function-local: saleha.core.loop's __init__ imports the deliberation
        # engine, which imports this module -- a module-level import is a cycle.
        from saleha.core.loop.self_healing import SelfHealingEngine
        self.healing_engine = SelfHealingEngine()

    def debug_code(self, task: str, code: str, error_log: str, tests: str = "") -> DebugResult:
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

If the failure is an assertion, the test's expected value can be wrong just as
easily as the implementation. Decide which one contradicts the task and fix
that one; never change a correct implementation to satisfy a wrong assertion.

Return exactly this format:
DIAGNOSIS: one concise explanation
FIXED_CODE:
```python
the complete corrected code
```
"""

        def build(content: str) -> Tuple[Tuple[str, str], List[ac.Check]]:
            diagnosis = re.search(r"^DIAGNOSIS:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
            fixed = self._extract_code(content)
            checks = [ac.check_python(fixed, "fixed code compiles")]
            if checks[0].status == ac.PASS:
                checks.append(ac.run_tests(fixed, tests) if tests.strip()
                              else ac.Check("tests pass", ac.NOT_RUN, "no tests were given"))
            return (diagnosis.group(1).strip() if diagnosis else "", fixed), checks

        got, checks, response, _rounds = ac.produce(self, prompt, build)
        if got is None:
            return DebugResult(success=False, error=response.error_message or "no answer",
                               model_used=response.model_used, checks=ac.as_dicts(checks))
        diagnosis, fixed_code = got
        if not fixed_code:
            return DebugResult(success=False, diagnosis=diagnosis, error="Model returned no corrected code.",
                               model_used=response.model_used, checks=ac.as_dicts(checks))
        return DebugResult(success=True, diagnosis=diagnosis, fixed_code=fixed_code,
                           model_used=response.model_used, checks=ac.as_dicts(checks),
                           verified=ac.verdict(checks))

    @staticmethod
    def _extract_code(response: str) -> str:
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""
