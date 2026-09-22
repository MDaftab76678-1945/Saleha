"""Tests for saleha/core/test_arbiter.py.

The fixtures are the two real `saleha run` failures from 2026-09-23: in both,
the model wrote a correct is_palindrome and a wrong assertion for it.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from saleha.core.harness.code_executor import CodeExecutor
from saleha.core.test_arbiter import arbitrate_failure, extract_failing_expectation

PALINDROME = (
    "def is_palindrome(s: str) -> bool:\n"
    "    s = ''.join(c for c in s if c.isalnum()).lower()\n"
    "    return s == s[::-1]\n"
)

DEEPSEEK_CODE = PALINDROME + (
    "\nassert is_palindrome('A man, a plan, a canal; Panama')\n"
    "assert not is_palindrome('race car')                    # False (fixed)\n"
)
DEEPSEEK_ERROR = (
    "Traceback (most recent call last):\n"
    '  File "C:\\Temp\\tmpkeioucpt.py", line 10, in <module>\n'
    "    assert not is_palindrome('race car')                    # False (fixed)\n"
    "           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
    "AssertionError\n"
)

UNITTEST_ERROR = (
    "FAIL: test_x (__main__.TestIsPalindrome.test_x)\n"
    "Traceback (most recent call last):\n"
    '  File "C:\\Temp\\tmpzzxdj6lo.py", line 32, in test_x\n'
    '    self.assertTrue(is_palindrome("#a@C#"))  # Fixed the expected result to True\n'
    "AssertionError: False is not true\n"
)


def _run_real(snippet: str) -> Tuple[bool, str]:
    res = CodeExecutor(timeout=15, audit=False).execute(snippet)
    return res.success and not res.blocked, res.output


def _answer(value: str):
    asked: List[str] = []

    def ask(prompt: str) -> str:
        asked.append(prompt)
        return f"Stripping gives the same string.\nANSWER: {value}"

    return ask, asked


@pytest.mark.parametrize(
    "line, call, expected",
    [
        ("assert not is_palindrome('race car')  # x", "is_palindrome('race car')", False),
        ('self.assertTrue(is_palindrome("#a@C#"))  # note', "is_palindrome('#a@C#')", True),
        ("assert is_palindrome('ab') == False", "is_palindrome('ab')", False),
        ("self.assertEqual(is_palindrome('aa'), True)", "is_palindrome('aa')", True),
        ("assert is_palindrome('x')", "is_palindrome('x')", True),
    ],
)
def test_extracts_call_and_expected_value(line: str, call: str, expected: bool) -> None:
    error = f'  File "t.py", line 3, in <module>\n    {line}\nAssertionError\n'

    exp = extract_failing_expectation(PALINDROME, error)

    assert exp is not None
    assert exp.call_src == call
    assert exp.expected is expected


@pytest.mark.parametrize(
    "line",
    [
        "assert is_palindrome(word)",           # argument is not a literal
        "assert helper('x')",                   # function not defined in the code
        "assert len('abc') == 3",               # builtin, not the code under test
        "x = 1",                                # not an assertion
    ],
)
def test_skips_assertions_it_cannot_check(line: str) -> None:
    error = f'  File "t.py", line 3, in <module>\n    {line}\nAssertionError\n'

    assert extract_failing_expectation(PALINDROME, error) is None


def test_blames_the_test_when_independent_answer_matches_the_code() -> None:
    ask, asked = _answer("True")

    verdict = arbitrate_failure("Write is_palindrome ignoring case and punctuation",
                                DEEPSEEK_CODE, DEEPSEEK_ERROR, _run_real, ask)

    assert verdict is not None
    assert verdict.blame == "test"
    assert verdict.actual is True
    assert verdict.expectation.expected is False
    assert "TEST is wrong" in verdict.note
    # The independent question shows neither the code nor the assertion.
    assert "def is_palindrome" not in asked[0] and "assert" not in asked[0]


def test_blames_the_implementation_when_answer_matches_the_test() -> None:
    ask, _ = _answer("False")

    verdict = arbitrate_failure("task", DEEPSEEK_CODE, DEEPSEEK_ERROR, _run_real, ask)

    assert verdict is not None
    assert verdict.blame == "implementation"
    assert "IMPLEMENTATION is wrong" in verdict.note


def test_unittest_failure_is_arbitrated_too() -> None:
    ask, _ = _answer("False")

    verdict = arbitrate_failure("task", PALINDROME, UNITTEST_ERROR, _run_real, ask)

    assert verdict is not None
    assert verdict.blame == "test"
    assert verdict.actual is False


@pytest.mark.parametrize("reply", ["I think it is true", "ANSWER: maybe", ""])
def test_no_verdict_without_a_parseable_independent_answer(reply: str) -> None:
    verdict = arbitrate_failure("task", DEEPSEEK_CODE, DEEPSEEK_ERROR, _run_real, lambda p: reply)

    assert verdict is None


def test_no_verdict_when_answer_matches_neither_side() -> None:
    verdict = arbitrate_failure("task", DEEPSEEK_CODE, DEEPSEEK_ERROR, _run_real,
                                lambda p: "ANSWER: 'palindrome'")

    assert verdict is None


def test_no_verdict_when_the_implementation_cannot_run() -> None:
    broken = "def is_palindrome(s):\n    return undefined_name\n"

    verdict = arbitrate_failure("task", broken, DEEPSEEK_ERROR, _run_real, lambda p: "ANSWER: True")

    assert verdict is None
