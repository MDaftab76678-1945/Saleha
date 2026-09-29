"""Proof receipts on real throwaway git repos: each verdict, from real test runs."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from saleha.core import proof_receipt as pr

BUGGY = "def double(x):\n    return x * 2\n\n\ndef triple(x):\n    return x * 2\n"
FIXED = "def double(x):\n    return x * 2\n\n\ndef triple(x):\n    return x * 3\n"
BASE_TESTS = "from calc import double\n\n\ndef test_double():\n    assert double(3) == 6\n"


def _git(root: str, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=root,
                   check=True, capture_output=True)


class ProofReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = os.path.join(self._tmp.name, "repo")
        os.makedirs(self.root)
        self._write("calc.py", BUGGY)
        self._write("test_calc.py", BASE_TESTS)
        _git(self.root, "init", "-q")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, rel: str, text: str) -> None:
        Path(self.root, rel).write_text(text, encoding="utf-8")

    def _receipt(self) -> pr.Receipt:
        side = self._tmp.name
        return pr.make_receipt(self.root, timeout=120,
                               ledger_path=os.path.join(side, "work.jsonl"),
                               anchor_path=os.path.join(side, "anchor.jsonl"))

    def test_fix_with_a_guarding_test_is_proven(self) -> None:
        self._write("calc.py", FIXED)
        self._write("test_calc.py", BASE_TESTS.replace("import double", "import double, triple")
                    + "\n\ndef test_triple():\n    assert triple(2) == 6\n")
        r = self._receipt()
        self.assertEqual(r.verdict, pr.PROVEN, r.reason)
        assert r.head_run is not None and r.base_run is not None and r.control_run is not None
        self.assertTrue(r.head_run.passed)
        self.assertFalse(r.base_run.passed)
        self.assertTrue(r.control_run.passed, r.control_run.tail)
        self.assertTrue(r.ledger_entry)
        self.assertIn("(control)", pr.render_markdown(r))

    def test_change_the_tests_do_not_notice_is_unproven(self) -> None:
        self._write("calc.py", FIXED)          # triple fixed, but no test covers it
        r = self._receipt()
        self.assertEqual(r.verdict, pr.UNPROVEN, r.reason)
        self.assertIn("with AND without", r.reason)
        self.assertIsNone(r.control_run)       # the base run passed: no control needed

    def test_a_checkout_that_cannot_run_the_suite_is_not_a_proof(self) -> None:
        """The base run dies because a git-ignored file is missing from the clean
        checkout, not because the change is missing. Before the control run this
        came back PROVEN for a comment-only edit no test can notice."""
        self._write(".gitignore", "local_cfg.py\n")
        self._write("local_cfg.py", "FACTOR = 2\n")      # ignored: in the tree, in no checkout
        self._write("calc.py", "from local_cfg import FACTOR\n\n\ndef double(x):\n"
                               "    return x * FACTOR\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "depend on an ignored file")
        self._write("calc.py", Path(self.root, "calc.py").read_text(encoding="utf-8")
                    + "\n\n# a change no test can notice\n")
        r = self._receipt()
        self.assertEqual(r.verdict, pr.NOT_CHECKED, r.reason)
        self.assertIn("clean checkout", r.reason)
        self.assertIn("local_cfg", r.reason)             # says why, from the control run
        assert r.head_run is not None and r.base_run is not None and r.control_run is not None
        self.assertTrue(r.head_run.passed)
        self.assertFalse(r.base_run.passed)
        self.assertFalse(r.control_run.passed)

    def test_a_control_that_could_not_run_is_not_a_proof(self) -> None:
        self._write("calc.py", FIXED)
        failed = pr.TestRun(True, False, 1, "1 failed", 0.1)
        no_worktree = pr.TestRun(False, False, None, "git worktree failed: disk full", 0.0)
        with mock.patch.object(pr, "_run_at_base", side_effect=[failed, no_worktree]):
            r = self._receipt()
        self.assertEqual(r.verdict, pr.NOT_CHECKED, r.reason)
        self.assertIn("disk full", r.reason)

    def test_breaking_change_is_failing(self) -> None:
        self._write("calc.py", BUGGY.replace("return x * 2\n\n\ndef", "return x\n\n\ndef"))
        r = self._receipt()
        self.assertEqual(r.verdict, pr.FAILING, r.reason)

    def test_weakened_tests_are_unproven_even_when_they_guard(self) -> None:
        self._write("calc.py", FIXED)
        self._write("test_calc.py",
                    "from calc import triple\n\n\ndef test_triple():\n    assert triple(2) == 6\n")
        r = self._receipt()
        self.assertEqual(r.verdict, pr.UNPROVEN, r.reason)
        self.assertTrue(any("removed" in w for w in r.weakening), r.weakening)

    def test_racy_change_carries_a_concurrency_warning(self) -> None:
        self._write("worker.py", "import threading\nhits = 0\n\n\ndef work():\n    global hits\n"
                                 "    hits += 1\n\n\ndef total():\n    return hits\n\n\n"
                                 "threading.Thread(target=work)\n")
        r = self._receipt()
        self.assertTrue(any("C001" in w for w in r.concurrency), r.concurrency)
        self.assertIn("Concurrency warnings: worker.py", pr.render_markdown(r))

    def test_no_change_is_not_checked(self) -> None:
        r = self._receipt()
        self.assertEqual(r.verdict, pr.NOT_CHECKED)
        self.assertIn("nothing to prove", r.reason)

    def test_not_a_repo_is_not_checked(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as bare:
            r = pr.make_receipt(bare)
        self.assertEqual(r.verdict, pr.NOT_CHECKED)
        self.assertIn("not a git repository", r.reason)

    def test_working_tree_is_left_untouched(self) -> None:
        self._write("calc.py", FIXED)
        self._receipt()
        self.assertEqual(Path(self.root, "calc.py").read_text(encoding="utf-8"), FIXED)
        worktrees = subprocess.run(["git", "worktree", "list"], cwd=self.root,
                                   capture_output=True, text=True, check=True).stdout
        self.assertEqual(len(worktrees.strip().splitlines()), 1, worktrees)


if __name__ == "__main__":
    unittest.main()
