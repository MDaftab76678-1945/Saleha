"""
Saleha Agents: QA Lead & Test Automation Agent

Synthesizes high-coverage test suites (unit, integration, regression, property-based)
with parameterized test cases and sandboxed verification assertions.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List

from saleha.agents.base_agent import AgentResponse, BaseAgent


def api_summary(code: str) -> str:
    """
    Signatures and docstrings of the top-level functions and classes in `code`.

    QA is given this, not the full source. With the full source in the
    prompt, small models pasted it into the test file (so the tests checked
    their own copy) and wrote tests that mirror the implementation instead
    of the task. Falls back to the full code if it does not parse.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return code
    out: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            out.append(_signature(node, indent=""))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("Test"):
            out.append(f"class {node.name}:")
            doc = ast.get_docstring(node)
            if doc:
                out.append(f'    """{doc.splitlines()[0]}"""')
            methods = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and (not m.name.startswith("_") or m.name == "__init__")]
            out.extend(_signature(m, indent="    ") for m in methods)
            if not methods:
                out.append("    ...")
    return "\n".join(out) or code


def _signature(node: ast.stmt, indent: str) -> str:
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    line = f"{indent}{prefix} {node.name}({ast.unparse(node.args)}){returns}:"
    doc = ast.get_docstring(node)
    body = f'{indent}    """{doc.splitlines()[0]}"""' if doc else f"{indent}    ..."
    return f"{line}\n{body}"


@dataclass
class QATestSuite:
    task: str
    framework: str  # what the tests were asked to use; always "unittest" now
    test_code: str
    test_case_count: int
    edge_cases_covered: List[str]
    model_used: str = ""
    # False when no model wrote tests; test_code is then empty and `error`
    # says why. Callers must treat that as "tests did not run", never a pass.
    generated: bool = True
    error: str = ""


class QALeadAgent(BaseAgent):
    """Lead QA Engineer & Autonomous Test Automation Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="QALead", model=model)

    def generate_test_suite(self, task: str, code: str, framework: str = "unittest") -> QATestSuite:
        """Write unittest tests for `task` against the API in `code`. See api_summary for why only the API.

        `framework` is accepted for old callers and ignored: the structured
        runner needs no fixtures from unittest, and pytest may be absent in a
        sandbox image.
        """
        framework = "unittest"
        prompt = f"""You are a QA engineer. Write a Python unittest test suite that checks this task:
Task: {task}

The code under test is ALREADY DEFINED in the same module. Its API:
```python
{api_summary(code)}
```
Rules:
1. Do NOT redefine, copy or import the functions/classes above -- call them directly.
2. Test only behaviour the task states. Do not invent behaviour for inputs the task
   does not mention (for example None or wrong types) unless the task defines it.
3. Include happy paths and the edge cases the task implies (empty input, boundaries).
4. Use `import unittest` and unittest.TestCase classes. Do not import sys, os or subprocess.
5. Reply with a single ```python code block and nothing else.
"""
        resp: AgentResponse = self.think(prompt)

        # No model answer means no tests. This used to substitute a suite of
        # `assert True` functions, which (with the swarm's placeholder code)
        # let a pipeline report "tests PASSED" with no model reachable at all.
        if not resp.success or not (resp.content or "").strip():
            return QATestSuite(
                task=task,
                framework=framework,
                test_code="",
                test_case_count=0,
                edge_cases_covered=[],
                model_used=resp.model_used,
                generated=False,
                error=resp.error_message or "model returned no test code",
            )

        test_content = self._extract_code(resp.content)
        # Counted from the code, not assumed: the old `or 3` reported three
        # tests for a suite that had none, and the edge-case list was a fixed
        # claim made whatever the tests contained -- so it is left empty.
        test_count = len(re.findall(r"def test\w*", test_content))

        return QATestSuite(
            task=task,
            framework=framework,
            test_code=test_content,
            test_case_count=test_count,
            edge_cases_covered=[],
            model_used=resp.model_used,
        )

    @staticmethod
    def _extract_code(content: str) -> str:
        """The fenced Python block(s) if the model used fences, else the text as-is."""
        blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", content, re.DOTALL)
        return "\n\n".join(b.strip() for b in blocks) if blocks else content.strip()
