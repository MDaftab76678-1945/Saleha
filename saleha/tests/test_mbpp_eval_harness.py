"""The MBPP harness must not grade a candidate that skipped or failed its tests."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any, Dict

_SPEC = importlib.util.spec_from_file_location(
    "mbpp_eval", Path(__file__).resolve().parents[2] / "scripts" / "mbpp_eval.py")
assert _SPEC is not None and _SPEC.loader is not None
mbpp_eval = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mbpp_eval)

TASK: Dict[str, Any] = {
    "test_setup_code": "",
    "test_list": ["assert add(1, 2) == 3", "assert add(-1, 1) == 0"],
}


class RunTestsTests(unittest.TestCase):
    def test_correct_code_passes(self) -> None:
        self.assertTrue(mbpp_eval.run_tests("def add(a, b):\n    return a + b", TASK)["passed"])

    def test_wrong_code_fails_with_the_assertion(self) -> None:
        res = mbpp_eval.run_tests("def add(a, b):\n    return a - b", TASK)
        self.assertFalse(res["passed"])
        self.assertIn("AssertionError", res["reason"])

    def test_exiting_before_the_asserts_is_not_a_pass(self) -> None:
        for escape in ("import sys\nsys.exit(0)", "import os\nos._exit(0)"):
            res = mbpp_eval.run_tests(escape, TASK)
            self.assertFalse(res["passed"], escape)

    def test_endless_loop_times_out(self) -> None:
        res = mbpp_eval.run_tests("while True:\n    pass", TASK, timeout=2)
        self.assertFalse(res["passed"])
        self.assertIn("timeout", res["reason"])

    def test_empty_code_fails(self) -> None:
        self.assertEqual(mbpp_eval.run_tests("  \n", TASK),
                         {"passed": False, "reason": "empty code"})

    def test_extract_code_takes_the_fenced_block(self) -> None:
        reply = "Here:\n```python\ndef add(a, b):\n    return a + b\n```\nDone."
        self.assertEqual(mbpp_eval.extract_code(reply), "def add(a, b):\n    return a + b")


if __name__ == "__main__":
    unittest.main()
