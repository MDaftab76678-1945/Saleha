"""Tourist solver: few model calls, success only from a real test run."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

from saleha.core import tourist_solver as ts

TESTS = "from solution import *\n\n\ndef test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n"
GOOD = "```python\ndef add(a, b):\n    return a + b\n```"
BAD = "```python\ndef add(a, b):\n    return a - b\n```"


class _Scripted:
    def __init__(self, replies: List[str]) -> None:
        self.replies = list(replies)
        self.calls: List[Tuple[str, bool]] = []

    def __call__(self, model: str, _prompt: str, reasoning: bool) -> str:
        self.calls.append((model, reasoning))
        return self.replies.pop(0) if self.replies else ""


class TouristSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        (self.root / "solution.py").write_text("", encoding="utf-8")
        (self.root / "test_solution.py").write_text(TESTS, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_understand_reads_the_tests_without_a_model(self) -> None:
        u, why = ts.understand(str(self.root))
        assert u is not None, why
        self.assertEqual(u.target, "solution.py")
        self.assertEqual(u.required_names, ["add"])
        self.assertIn("assert add(2, 3) == 5", u.asserts)

    def test_correct_first_answer_takes_one_call(self) -> None:
        think = _Scripted([GOOD])
        r = ts.solve("add two numbers", str(self.root), think=think)
        self.assertEqual(r.verdict, "SOLVED", r.reason)
        self.assertEqual(r.model_calls, 1)
        self.assertEqual(think.calls, [(ts.FAST_MODEL, False)])

    def test_repair_escalates_to_the_deep_model_second(self) -> None:
        think = _Scripted([BAD, BAD, GOOD])
        r = ts.solve("add two numbers", str(self.root), think=think)
        self.assertEqual(r.verdict, "SOLVED", r.reason)
        # Reasoning off on the deep call too: with it, qwen3:8b timed out
        # (300 s) on every measured task.
        self.assertEqual(think.calls, [(ts.FAST_MODEL, False), (ts.FAST_MODEL, False),
                                       (ts.DEEP_MODEL, False)])

    def test_never_solved_without_passing_tests(self) -> None:
        r = ts.solve("add two numbers", str(self.root), think=_Scripted([BAD, BAD, BAD]))
        self.assertFalse(r.success)
        self.assertEqual(r.verdict, "FAILED")
        self.assertIn("tests still fail", r.reason)

    def test_no_code_block_is_a_failure_not_a_pass(self) -> None:
        r = ts.solve("add two numbers", str(self.root), think=_Scripted(["I think it is done."]))
        self.assertEqual(r.verdict, "FAILED")

    def test_solution_that_rewrites_the_tests_is_rejected(self) -> None:
        cheat = ("```python\nimport pathlib\n"
                 "pathlib.Path(__file__).with_name('test_solution.py').write_text("
                 "'def test_ok():\\n    pass\\n')\n"
                 "def add(a, b):\n    return 0\n```")
        r = ts.solve("add two numbers", str(self.root), think=_Scripted([cheat] * 3))
        self.assertFalse(r.success)
        self.assertIn("test files changed", r.attempts[0].detail + r.reason)

    def test_failed_attempt_is_rolled_back_when_asked(self) -> None:
        (self.root / "solution.py").write_text("# original\n", encoding="utf-8")
        r = ts.solve("add two numbers", str(self.root), think=_Scripted([BAD] * 3),
                     restore_on_failure=True)
        self.assertFalse(r.success)
        self.assertEqual((self.root / "solution.py").read_text(encoding="utf-8"), "# original\n")

    def test_rewrite_that_drops_other_definitions_is_rejected(self) -> None:
        (self.root / "solution.py").write_text("def keep_me():\n    return 1\n", encoding="utf-8")
        r = ts.solve("add two numbers", str(self.root), think=_Scripted([GOOD] * 3))
        self.assertFalse(r.success)
        self.assertIn("keep_me", r.attempts[0].detail)
        kept = GOOD.replace("```python\n", "```python\ndef keep_me():\n    return 1\n\n\n")
        r = ts.solve("add two numbers", str(self.root), think=_Scripted([kept]))
        self.assertTrue(r.success, r.reason)

    def test_explicit_model_is_used_for_every_call(self) -> None:
        think = _Scripted([BAD, BAD, GOOD])
        ts.solve("add", str(self.root), think=think, fast_model="m1", deep_model="m1")
        self.assertEqual({m for m, _ in think.calls}, {"m1"})

    def test_time_budget_stops_further_calls(self) -> None:
        think = _Scripted([BAD, BAD, GOOD])
        r = ts.solve("add", str(self.root), think=think, time_budget=0)
        self.assertEqual(r.model_calls, 1)
        self.assertIn("time budget", r.reason)

    def test_unreachable_model_is_reported_as_such(self) -> None:
        def down(model: str, _prompt: str, reasoning: bool) -> str:
            raise ts.ModelCallError("Gemini HTTP 503: high demand")
        r = ts.solve("add", str(self.root), think=down)
        self.assertFalse(r.success)
        self.assertIn("model call failed: Gemini HTTP 503", r.reason)
        self.assertNotIn("no code block", r.reason)

    def test_folder_without_tests_is_not_run(self) -> None:
        (self.root / "test_solution.py").unlink()
        r = ts.solve("x", str(self.root), think=_Scripted([GOOD]))
        self.assertEqual(r.verdict, "NOT_RUN")
        self.assertEqual(r.model_calls, 0)


if __name__ == "__main__":
    unittest.main()
