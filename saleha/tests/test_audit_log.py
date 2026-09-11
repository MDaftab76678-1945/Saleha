"""Unit tests for saleha.core.audit_log.AuditLog. Had no test coverage
before this file (found during a test-coverage sweep of saleha/core/)."""

import json
import os
import tempfile
import unittest

from saleha.core.audit_log import AuditLog


class AuditLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp_dir, "audit.jsonl")
        self.log = AuditLog(path=self.path)

    def test_recent_on_a_fresh_log_is_empty(self) -> None:
        self.assertEqual(self.log.recent(), [])

    def test_record_writes_one_jsonl_line_per_entry(self) -> None:
        self.log.record(code="print('hi')", allowed=True, executed=True, success=True, exit_code=0)
        self.log.record(code="import socket", allowed=False, reason="network access blocked")

        with open(self.path, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0]["allowed"])
        self.assertFalse(lines[1]["allowed"])
        self.assertEqual(lines[1]["reason"], "network access blocked")

    def test_record_stores_both_a_hash_and_a_preview(self) -> None:
        # AuditLog deliberately keeps a preview (for a human reviewing what
        # ran) alongside a hash (for exact-match lookups) -- it does not
        # redact the code, by design (this is a local execution log, not a
        # secrets store).
        self.log.record(code="print('hello')", allowed=True)
        entries = self.log.recent()
        self.assertEqual(len(entries[0]["code_hash"]), 16)
        self.assertIn("print('hello')", entries[0]["code_preview"])

    def test_record_preview_is_truncated_to_120_chars(self) -> None:
        long_code = "x = 1  # " + "y" * 200
        self.log.record(code=long_code, allowed=True)
        entries = self.log.recent()
        self.assertEqual(len(entries[0]["code_preview"]), 120)

    def test_recent_respects_the_limit_and_returns_newest_last(self) -> None:
        for i in range(5):
            self.log.record(code=f"x = {i}", allowed=True)
        recent = self.log.recent(n=2)
        self.assertEqual(len(recent), 2)
        self.assertIn("x = 4", recent[-1]["code_preview"])

    def test_blocked_entries_returns_only_disallowed_ones(self) -> None:
        self.log.record(code="ok_code", allowed=True)
        self.log.record(code="bad_code", allowed=False, reason="blocked")
        blocked = self.log.blocked_entries()
        self.assertEqual(len(blocked), 1)
        self.assertIn("bad_code", blocked[0]["code_preview"])

    def test_recent_skips_corrupt_lines_rather_than_crashing(self) -> None:
        self.log.record(code="good_entry", allowed=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("{not valid json\n")
        entries = self.log.recent()
        self.assertEqual(len(entries), 1)
        self.assertIn("good_entry", entries[0]["code_preview"])


if __name__ == "__main__":
    unittest.main()
