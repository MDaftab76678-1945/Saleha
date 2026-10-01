"""saleha decide: PROVEN answers come from running things; ESTIMATED ones say they are estimates."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List

from saleha.core import decide
from saleha.tests.agents.test_agentic_loop import ScriptedAgent, _finish, _tool_call

PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def _git(root: str, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60).stdout


class AskTests(unittest.TestCase):
    def test_agreement_is_the_probability_and_it_is_labelled_an_estimate(self) -> None:
        replies = iter(["bug", "Bug.", "feature", "bug", "It is a bug report"])
        d = decide.ask("crash on empty list", "bug or feature?", ["bug", "feature"],
                       samples=5, think=lambda _m, _p: next(replies))
        self.assertEqual(d.kind, decide.ESTIMATED)
        self.assertEqual(d.answer, "bug")
        self.assertEqual(d.probabilities, {"bug": 0.8, "feature": 0.2})
        self.assertIn("not a proof", d.reason)

    def test_no_single_choice_named_means_undecided_not_a_guess(self) -> None:
        d = decide.ask("x", "yes or no?", ["yes", "no"], samples=3,
                       think=lambda _m, _p: "yes and no, it depends")
        self.assertIsNone(d.answer)

    def test_a_tie_is_undecided(self) -> None:
        replies = iter(["yes", "no"])
        d = decide.ask("x", "?", ["yes", "no"], samples=2, think=lambda _m, _p: next(replies))
        self.assertIsNone(d.answer)
        self.assertIn("tied", d.reason)

    def test_failed_calls_are_missing_votes_not_a_crash(self) -> None:
        def boom(_m: str, _p: str) -> str:
            raise RuntimeError("model offline")
        d = decide.ask("x", "?", ["yes", "no"], samples=2, think=boom)
        self.assertIsNone(d.answer)
        self.assertIn("model offline", d.reason)


class ProvenAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return a - b\n")
        Path(self.root, "test_calc.py").write_bytes(b"from calc import add\n\n\ndef test_ok():\n    assert True\n")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            _git(self.root, *args)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_flaky_versus_stable_failure(self) -> None:
        counter = os.path.join(self.root, "..", os.path.basename(self.root) + "-count")
        script = os.path.join(self.root, "..", os.path.basename(self.root) + "-alternate.py")
        Path(script).write_text(
            "import os, sys\np = sys.argv[1]\nn = int(open(p).read()) if os.path.exists(p) else 0\n"
            "open(p, 'w').write(str(n + 1))\nsys.exit(n % 2)\n", encoding="utf-8")
        d = decide.is_flaky(self.root, [sys.executable, script, counter], runs=4)
        self.assertEqual((d.kind, d.answer), (decide.PROVEN, "FLAKY"))
        self.assertEqual((d.evidence["passed"], d.evidence["failed"]), (2, 2))
        d = decide.is_flaky(self.root, [sys.executable, "-c", "import sys; sys.exit(1)"], runs=3)
        self.assertEqual(d.answer, "STABLE_FAIL")
        for p in (counter, script):
            Path(p).unlink(missing_ok=True)

    def test_a_reproduced_report_is_real_and_the_tree_is_left_clean(self) -> None:
        repro = "from calc import add\n\n\ndef test_reported():\n    assert add(2, 3) == 5\n"
        agent = ScriptedAgent([_tool_call("write_file", path="test_saleha_repro.py", content=repro)]
                              + [_finish("written")] * 4)
        d = decide.is_real_bug(self.root, "add(2, 3) returns -1", model="scripted", test_command=PYTEST,
                               agent_factory=lambda _m: agent, max_steps=6, timeout=120, attempts=1)
        self.assertEqual((d.kind, d.answer), (decide.PROVEN, "REAL"), d.reason)
        self.assertIn("assert add(2, 3) == 5", d.evidence["test_source"])
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_not_reproduced_is_undecided_never_not_a_bug(self) -> None:
        passing = "from calc import add\n\n\ndef test_x():\n    assert add(1, 1) == 0\n"
        agent = ScriptedAgent([_tool_call("write_file", path="test_saleha_repro.py", content=passing)]
                              + [_finish("w")] * 4)
        d = decide.is_real_bug(self.root, "add is wrong", model="scripted", test_command=PYTEST,
                               agent_factory=lambda _m: agent, max_steps=6, timeout=120, attempts=1)
        self.assertIsNone(d.answer)
        self.assertIn("does not show the bug is unreal", d.reason)

    def test_is_proven_reads_the_receipt(self) -> None:
        d = decide.is_proven(self.root, "HEAD", PYTEST)
        self.assertEqual(d.kind, decide.PROVEN)
        self.assertIsNone(d.answer)                    # nothing changed: NOT_CHECKED
        self.assertIn("nothing to prove", d.reason)


if __name__ == "__main__":
    unittest.main()
