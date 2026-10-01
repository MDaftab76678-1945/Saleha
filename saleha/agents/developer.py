"""
Saleha Agents: Developer Agent

Writes the code for a task together with tests for it, and runs the tests
on the code before calling it done. When they fail, the model is shown the
failures and asked once more. Python code is run (after the AST security
screen, in a throwaway directory); for other languages only the answer's
shape is checked and the result says the code was not run.

The dependencies listed are the third-party modules the code imports, read
from it -- not a fixed list.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class DeveloperOutput:
    task: str
    language: str
    source_code: str
    files_created: List[str]
    dependencies: List[str]
    model_used: str = ""
    test_code: str = ""
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None      # True: the tests ran and passed on this code
    is_placeholder: bool = False         # True: no model answered; source_code does nothing


def third_party_imports(code: str) -> List[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    stdlib = getattr(sys, "stdlib_module_names", set())
    return sorted(n for n in names if n not in stdlib and n not in ("solution", "__future__"))


class DeveloperAgent(BaseAgent):
    """Principal Polyglot Software Developer Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Developer", model=model)

    def develop_feature(self, task: str, language: str = "python",
                        existing_context: Optional[str] = None) -> DeveloperOutput:
        """Code and tests for `task`; for Python the tests are run on the code."""
        python = language.lower() in ("python", "py")
        ctx = f"\nExisting context:\n{existing_context[:4000]}\n" if existing_context else ""
        prompt = (
            f"Write clean, typed {language} code for this task:\n{task}\n{ctx}\n"
            + ("Answer with exactly two fenced ```python blocks:\n"
               "1. the implementation (a module named solution.py; no code runs at import time)\n"
               "2. pytest tests for it: `from solution import ...`, plain `assert`s, covering normal cases "
               "and the edge cases the task implies\n" if python else
               f"Answer with two fenced blocks: the {language} implementation, then its tests.\n")
            + "No other text.")

        def build(content: str) -> Tuple[Tuple[str, str], List[ac.Check]]:
            blocks = [b for _i, b in ac.fenced_blocks(content)]
            if not blocks and content.strip():
                blocks = [content.strip()]
            code = next((b for b in blocks if "def test" not in b), blocks[0] if blocks else "")
            tests = next((b for b in blocks if "def test" in b and b is not code), "")
            if not tests and "def test" in code:
                tests = "from solution import *  # noqa\n"     # the tests sit in the code's own block
            if not python:
                return (code, tests), [ac.Check("code written", ac.PASS if code else ac.FAIL),
                                       ac.Check("tests pass", ac.NOT_RUN, f"{language} code is not run here")]
            checks = [ac.check_python(code)]
            if checks[0].status != ac.PASS:
                checks.append(ac.Check("tests pass", ac.NOT_RUN, "the code does not compile"))
            elif not tests.strip():
                # Tests were asked for: an answer without them fails, so the model is asked again.
                checks.append(ac.Check("tests pass", ac.FAIL, "no tests were written"))
            else:
                checks.append(ac.run_tests(code, tests))
            return (code, tests), checks

        files, checks, resp, _rounds = ac.produce(self, prompt, build)
        if files is None or not files[0].strip():
            # No model answer: an explicitly labelled placeholder, never a passing implementation.
            code = (f"# Offline placeholder for: {task}\n# No model produced code; this stub does nothing.\n\n"
                    "def execute():\n    raise NotImplementedError(\"placeholder -- no implementation generated\")\n")
            return DeveloperOutput(task=task, language=language, source_code=code, files_created=[],
                                   dependencies=[], model_used=resp.model_used,
                                   checks=ac.as_dicts(ac.fallback_note(checks, files is not None)),
                                   verified=None, is_placeholder=True)
        code, tests = files
        return DeveloperOutput(
            task=task, language=language, source_code=code, files_created=[],
            dependencies=third_party_imports(code) if python else [],
            model_used=resp.model_used, test_code=tests, checks=ac.as_dicts(checks),
            verified=ac.verdict(checks))
