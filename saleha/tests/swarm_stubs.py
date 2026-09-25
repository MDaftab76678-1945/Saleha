"""Agent stubs for swarm / octopus pipeline tests.

The pipeline tests used to run the real agents with model="mock", which the
provider sends to Ollama as a model that does not exist. The Coder always
failed, and the pipelines hid that behind a placeholder `def execute():
return True` plus `assert True` tests that were never even called -- so the
tests were asserting the placeholder. These stubs give the pipelines real
code and real tests, so what is under test is the pipeline's own logic.
"""

from __future__ import annotations

import contextlib
from typing import Iterator, Optional
from unittest.mock import patch

from saleha.agents.coder import CodeResult
from saleha.agents.qa_lead import QATestSuite
from saleha.agents.reviewer import ReviewResult

GOOD_CODE = (
    "class TokenBucket:\n"
    "    def __init__(self, capacity):\n"
    "        self.tokens = capacity\n"
    "\n"
    "    def take(self):\n"
    "        if self.tokens <= 0:\n"
    "            return False\n"
    "        self.tokens -= 1\n"
    "        return True\n"
)

GOOD_TESTS = (
    "import unittest\n"
    "\n"
    "class TestTokenBucket(unittest.TestCase):\n"
    "    def test_take_until_empty(self):\n"
    "        bucket = TokenBucket(1)\n"
    "        self.assertTrue(bucket.take())\n"
    "        self.assertFalse(bucket.take())\n"
)

FAILING_TESTS = (
    "import unittest\n"
    "\n"
    "class TestTokenBucket(unittest.TestCase):\n"
    "    def test_wrong_expectation(self):\n"
    "        self.assertFalse(TokenBucket(1).take())\n"
)


@contextlib.contextmanager
def stub_agents(code: Optional[str] = GOOD_CODE, tests: Optional[str] = GOOD_TESTS,
                approved: bool = True) -> Iterator[None]:
    """Patch Coder / QALead / Reviewer. `code=None` or `tests=None` = that model failed."""
    def fake_code(*_a: object, **_k: object) -> CodeResult:
        if code is None:
            return CodeResult(success=False, code="", error="model unreachable")
        return CodeResult(success=True, code=code)

    def fake_suite(task: str, _code: str, framework: str = "unittest") -> QATestSuite:
        if tests is None:
            return QATestSuite(task=task, framework=framework, test_code="", test_case_count=0,
                               edge_cases_covered=[], generated=False, error="model unreachable")
        return QATestSuite(task=task, framework=framework, test_code=tests,
                           test_case_count=tests.count("def test"), edge_cases_covered=[])

    with patch("saleha.agents.coder.CoderAgent.generate_code", side_effect=fake_code), \
         patch("saleha.agents.qa_lead.QALeadAgent.generate_test_suite", side_effect=fake_suite), \
         patch("saleha.agents.reviewer.ReviewerAgent.review_code",
               return_value=ReviewResult(approved=approved, feedback="")):
        yield
