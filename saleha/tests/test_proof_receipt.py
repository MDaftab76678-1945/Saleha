"""Proof receipts on real throwaway git repos: each verdict, from real test runs."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

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
        assert r.head_run is not None and r.base_run is not None
        self.assertTrue(r.head_run.passed)
        self.assertFalse(r.base_run.passed)
        self.assertTrue(r.ledger_entry)

    def test_change_the_tests_do_not_notice_is_unproven(self) -> None:
        self._write("calc.py", FIXED)          # triple fixed, but no test covers it
        r = self._receipt()
        self.assertEqual(r.verdict, pr.UNPROVEN, r.reason)
        self.assertIn("with AND without", r.reason)

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
