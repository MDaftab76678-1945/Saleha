"""Tests for Per-Project Persistent Agent Memory and Decision Journal."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.project_memory import ProjectMemory, get_project_memory
from saleha.core.memory_journal import MemoryJournal


class ProjectMemoryTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem = ProjectMemory("test_project", memory_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_remember_and_recall(self):
        self.mem.remember("Use SQLite for session storage", category="decision", tags=["database"])
        results = self.mem.recall("SQLite")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "decision")

    def test_recall_by_category(self):
        self.mem.remember("Fixed TypeError by adding None check", category="fix", tags=["TypeError"])
        self.mem.remember("Architecture uses hexagonal pattern", category="decision")
        fixes = self.mem.recall("nonexistent_keyword", category="fix")
        self.assertEqual(len(fixes), 0)
        fixes2 = self.mem.recall("TypeError", category="fix")
        self.assertEqual(len(fixes2), 1)

    def test_recall_fixes(self):
        self.mem.remember("KeyError fixed by using .get()", category="fix", tags=["KeyError"])
        results = self.mem.recall_fixes("KeyError")
        self.assertGreaterEqual(len(results), 1)

    def test_recall_decisions(self):
        self.mem.remember("Use REST not GraphQL", category="decision")
        self.mem.remember("Use pytest for testing", category="decision")
        decisions = self.mem.recall_decisions()
        self.assertGreaterEqual(len(decisions), 2)

    def test_forget_entry(self):
        entry = self.mem.remember("Temporary note", category="fact")
        self.assertTrue(self.mem.forget(entry.entry_id))
        results = self.mem.recall("Temporary note")
        self.assertEqual(len(results), 0)

    def test_forget_nonexistent_returns_false(self):
        self.assertFalse(self.mem.forget("nonexistent_id"))

    def test_stats_structure(self):
        self.mem.remember("fact one", category="fact")
        self.mem.remember("fix one", category="fix")
        stats = self.mem.stats()
        self.assertEqual(stats["project"], "test_project")
        self.assertEqual(stats["total_entries"], 2)
        self.assertIn("fact", stats["categories"])

    def test_persistence_across_instances(self):
        self.mem.remember("Persisted decision", category="decision")
        mem2 = ProjectMemory("test_project", memory_dir=self.tmp)
        results = mem2.recall("Persisted")
        self.assertEqual(len(results), 1)

    def test_export_snapshot(self):
        self.mem.remember("Export me", category="fact")
        snap = self.mem.export_snapshot()
        self.assertIsInstance(snap, list)
        self.assertGreaterEqual(len(snap), 1)
        self.assertIn("entry_id", snap[0])

    def test_get_project_memory_registry(self):
        m1 = get_project_memory("proj_alpha")
        m2 = get_project_memory("proj_alpha")
        self.assertIs(m1, m2)


class MemoryJournalTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.journal = MemoryJournal("test_proj", session_id="sess_001", journal_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_log_and_read_session(self):
        self.journal.log("PlannerAgent", "plan", "Build auth system", "Created 5-step plan", success=True, duration_ms=120)
        entries = self.journal.read_session()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].agent, "PlannerAgent")
        self.assertTrue(entries[0].success)

    def test_read_only_current_session(self):
        self.journal.log("Agent", "code", "Task", "Done", success=True)
        other = MemoryJournal("test_proj", session_id="sess_other", journal_dir=self.tmp)
        other.log("Agent", "fix", "Other", "Fixed", success=False)
        entries = self.journal.read_session()
        self.assertEqual(len(entries), 1)

    def test_success_rate_calculation(self):
        self.journal.log("A", "plan", "t", "ok", success=True)
        self.journal.log("A", "code", "t", "ok", success=True)
        self.journal.log("A", "test", "t", "fail", success=False)
        rate = self.journal.success_rate()
        self.assertAlmostEqual(rate, 0.667, places=2)

    def test_replay_summary_format(self):
        self.journal.log("CoderAgent", "code", "Write auth", "auth.py created", success=True, duration_ms=450)
        summary = self.journal.replay_summary()
        self.assertIn("CoderAgent", summary)
        self.assertIn("sess_001", summary)
        self.assertIn("✅", summary)

    def test_empty_session_replay(self):
        j = MemoryJournal("empty_proj", session_id="empty_sess", journal_dir=self.tmp)
        summary = j.replay_summary()
        self.assertIn("No entries", summary)


if __name__ == "__main__":
    unittest.main()
