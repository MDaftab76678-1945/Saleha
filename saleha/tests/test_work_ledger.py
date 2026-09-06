"""
Tests for the verifiable work ledger (saleha/core/work_ledger.py).

The property under test is not "the log is written correctly" -- it is that
a stranger holding only the ledger file and the repo can re-establish, or
refute, what the agent claimed. So these tests re-verify from disk through
a fresh WorkLedger instance wherever the claim is about verification,
rather than asking the in-memory object that just made the record.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from saleha.core.work_ledger import (
    RECHECKABLE,
    ClaimKind,
    Verdict,
    WorkLedger,
)


class LedgerTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger_path = os.path.join(self.tmp, "work.jsonl")
        with open(os.path.join(self.tmp, "app.py"), "w") as f:
            f.write("def add(a, b):\n    return a + b\n")
        self.led = WorkLedger(self.ledger_path, root_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reopen(self):
        """A fresh reader, as a third party would have."""
        return WorkLedger(self.ledger_path, root_dir=self.tmp)


class RecordingTests(LedgerTestBase):
    def test_file_contains_records_and_confirms(self):
        _, ok = self.led.record_file_contains("m", "goal", "app.py", "return a + b")
        self.assertTrue(ok)
        v = self.reopen().verify()
        self.assertTrue(v["chain_intact"])
        self.assertEqual(v["verdicts"].get(Verdict.CONFIRMED.value), 1)

    def test_false_claim_is_refuted_not_recorded_as_true(self):
        """Recording a claim that is not true must not make it true."""
        _, ok = self.led.record_file_contains("m", "goal", "app.py", "NOT IN FILE")
        self.assertFalse(ok)
        v = self.reopen().verify()
        self.assertEqual(v["verdicts"].get(Verdict.FAILED.value), 1)
        self.assertEqual(v["proof_rate"], 0.0)

    def test_command_argv_survives_reverification(self):
        """
        Real bug this covers: joining argv into a string for re-execution
        lost quoting, so [python, -c, "import sys;sys.exit(0)"] re-ran as a
        SyntaxError and produced a false FAILED.
        """
        _, ok = self.led.record_command(
            "m", "goal", [sys.executable, "-c", "import sys;sys.exit(0)"])
        self.assertTrue(ok)
        v = self.reopen().verify()
        self.assertEqual(v["verdicts"].get(Verdict.CONFIRMED.value), 1,
                         f"argv round-trip failed: {v['results']}")

    def test_failing_command_is_recorded_as_failing(self):
        _, ok = self.led.record_command(
            "m", "goal", [sys.executable, "-c", "import sys;sys.exit(3)"])
        self.assertFalse(ok)
        v = self.reopen().verify()
        self.assertEqual(v["verdicts"].get(Verdict.FAILED.value), 1)

    def test_missing_binary_is_diverged_not_failed(self):
        """
        A command that cannot run here is not evidence the claim was false.
        Conflating the two would make every ledger look fraudulent on a
        machine with different tooling.
        """
        self.led.record_command("m", "goal", ["definitely-not-a-real-binary-xyz"])
        v = self.reopen().verify()
        self.assertEqual(v["verdicts"].get(Verdict.ENVIRONMENT_DIVERGED.value), 1)
        self.assertIsNone(v["verdicts"].get(Verdict.FAILED.value))

    def test_file_digest_detects_later_edit(self):
        self.led.record_file_digest("m", "goal", "app.py")
        self.assertEqual(self.reopen().verify()["verdicts"].get(
            Verdict.CONFIRMED.value), 1)

        with open(os.path.join(self.tmp, "app.py"), "a") as f:
            f.write("# changed\n")
        self.assertEqual(self.reopen().verify()["verdicts"].get(
            Verdict.FAILED.value), 1)

    def test_tests_claim_is_tagged_as_tests(self):
        self.led.record_tests("m", "goal",
                              [sys.executable, "-c", "import sys;sys.exit(0)"])
        entry = self.reopen()._entries[0]
        self.assertEqual(entry.claim["kind"], ClaimKind.TESTS_PASSED.value)


class AssertionsAreNotProofTests(LedgerTestBase):
    """The central rule: talking must not raise the proof rate."""

    def test_assertion_is_unverifiable_and_uncounted(self):
        self.led.record_assertion("m", "goal", "I fixed everything perfectly")
        v = self.reopen().verify()
        self.assertEqual(v["verdicts"].get(Verdict.UNVERIFIABLE.value), 1)
        self.assertEqual(v["checkable_claims"], 0)
        self.assertEqual(v["proof_rate"], 0.0)

    def test_many_assertions_cannot_inflate_proof_rate(self):
        self.led.record_file_contains("m", "goal", "app.py", "return a + b")
        for i in range(20):
            self.led.record_assertion("m", "goal", f"claim number {i}, all good")
        v = self.reopen().verify()
        # 21 entries, but only the one checkable claim counts.
        self.assertEqual(v["entries"], 21)
        self.assertEqual(v["checkable_claims"], 1)
        self.assertEqual(v["proof_rate"], 1.0)

    def test_assertion_kind_is_excluded_from_recheckable(self):
        self.assertNotIn(ClaimKind.ASSERTION, RECHECKABLE)


class TamperDetectionTests(LedgerTestBase):
    def _write_lines(self, lines):
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _lines(self):
        with open(self.ledger_path, encoding="utf-8") as f:
            return [l for l in f.read().splitlines() if l.strip()]

    def setUp(self):
        super().setUp()
        self.led.record_file_contains("m", "goal", "app.py", "return a + b")
        self.led.record_command(
            "m", "goal", [sys.executable, "-c", "import sys;sys.exit(0)"])
        self.led.record_assertion("m", "goal", "all good")

    def test_intact_chain_verifies(self):
        self.assertTrue(self.reopen().verify()["chain_intact"])

    def test_editing_a_claim_breaks_the_chain(self):
        lines = self._lines()
        d = json.loads(lines[2])
        d["claim"]["detail"] = "I fixed everything and ALL TESTS PASS"
        lines[2] = json.dumps(d, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False)
        self._write_lines(lines)

        v = self.reopen().verify()
        self.assertFalse(v["chain_intact"])
        self.assertIn("modified after signing", v["chain_detail"])
        self.assertEqual(v["verdicts"].get(Verdict.TAMPERED.value), 3)

    def test_deleting_an_entry_breaks_the_chain(self):
        lines = self._lines()
        del lines[1]
        self._write_lines(lines)
        self.assertFalse(self.reopen().verify()["chain_intact"])

    def test_reordering_entries_breaks_the_chain(self):
        lines = self._lines()
        lines[0], lines[1] = lines[1], lines[0]
        self._write_lines(lines)
        self.assertFalse(self.reopen().verify()["chain_intact"])

    def test_corrupt_line_is_surfaced_not_skipped(self):
        """A truncated line must not yield a clean-looking shorter chain."""
        lines = self._lines()
        lines[1] = "{not valid json"
        self._write_lines(lines)
        v = self.reopen().verify()
        self.assertFalse(v["chain_intact"])
        self.assertIn("corrupt", v["chain_detail"])

    def test_appending_a_forged_entry_breaks_the_chain(self):
        """An attacker appending a 'passing tests' entry must be caught."""
        lines = self._lines()
        forged = {"seq": 3, "actor": "m", "goal": "goal",
                  "claim": {"kind": ClaimKind.TESTS_PASSED.value,
                            "subject": "pytest", "detail": "exit 0 expected",
                            "observed": "exit 0", "tree_digest": "", "at": 0,
                            "argv": []},
                  "prev_hash": "deadbeef", "hash": "deadbeef", "version": 1}
        lines.append(json.dumps(forged, sort_keys=True, separators=(",", ":")))
        self._write_lines(lines)
        self.assertFalse(self.reopen().verify()["chain_intact"])

    def test_chain_only_verification_needs_no_repo(self):
        """recheck=False must work without re-running anything."""
        v = self.reopen().verify(recheck=False)
        self.assertTrue(v["chain_intact"])
        self.assertEqual(v["results"], [])


class ProofRateTests(LedgerTestBase):
    def test_proof_rate_counts_only_confirmed_over_checkable(self):
        self.led.record_file_contains("m", "g", "app.py", "return a + b")   # confirmed
        self.led.record_file_contains("m", "g", "app.py", "NOT PRESENT")    # failed
        self.led.record_assertion("m", "g", "trust me")                     # ignored
        v = self.reopen().verify()
        self.assertEqual(v["checkable_claims"], 2)
        self.assertEqual(v["independently_confirmed"], 1)
        self.assertEqual(v["proof_rate"], 0.5)

    def test_empty_ledger_is_zero_not_a_crash(self):
        v = self.reopen().verify()
        self.assertEqual(v["entries"], 0)
        self.assertEqual(v["proof_rate"], 0.0)
        self.assertTrue(v["chain_intact"])


class TreeDigestTests(LedgerTestBase):
    def test_digest_is_stable_for_an_unchanged_tree(self):
        self.assertEqual(self.led.tree_digest(), self.led.tree_digest())

    def test_digest_changes_when_source_changes(self):
        before = self.led.tree_digest()
        with open(os.path.join(self.tmp, "app.py"), "a") as f:
            f.write("# edit\n")
        self.assertNotEqual(before, self.led.tree_digest())

    def test_dirty_git_tree_does_not_masquerade_as_its_commit(self):
        """A dirty checkout must fingerprint differently from a clean one."""
        try:
            for cmd in (["git", "init", "-q"],
                        ["git", "config", "user.email", "t@example.com"],
                        ["git", "config", "user.name", "T"],
                        ["git", "add", "."],
                        ["git", "commit", "-q", "-m", "init"]):
                subprocess.run(cmd, cwd=self.tmp, capture_output=True,
                               timeout=60, check=True)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git unavailable")

        clean = self.led.tree_digest()
        self.assertTrue(clean.startswith("git:"))
        with open(os.path.join(self.tmp, "app.py"), "a") as f:
            f.write("# dirty\n")
        self.assertNotEqual(clean, self.led.tree_digest())


if __name__ == "__main__":
    unittest.main()
