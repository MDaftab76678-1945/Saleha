"""Unit tests for Automated SemVer Changelog Generator."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.changelog_generator import ChangelogGenerator, ReleaseSection


class ChangelogGeneratorTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.generator = ChangelogGenerator(repo_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_categorize_conventional_commits(self):
        commits = [
            "feat: Implement distributed GPU swarm server",
            "fix: Resolve deadlock in repo watcher",
            "refactor: Rename symbol across files",
            "perf: Sub-10ms semantic search",
            "test: Add browser UI test suites",
            "docs: Update README with 437 tests"
        ]
        cat = self.generator.categorize_commits(commits)
        self.assertEqual(len(cat.features), 1)
        self.assertEqual(len(cat.fixes), 1)
        self.assertEqual(len(cat.refactors), 1)
        self.assertEqual(len(cat.performance), 1)
        self.assertEqual(len(cat.tests), 1)
        self.assertEqual(len(cat.docs), 1)

    def test_generate_release_notes_markdown(self):
        notes = self.generator.generate_release_notes(version="1.5.0")
        self.assertIn("## [1.5.0]", notes)

    def test_update_changelog_file(self):
        changelog_file = os.path.join(self.temp_dir, "CHANGELOG.md")
        saved = self.generator.update_changelog_file(file_path=changelog_file, version="1.5.0")
        self.assertTrue(os.path.isfile(saved))
        with open(saved, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# Changelog", content)
        self.assertIn("## [1.5.0]", content)


if __name__ == "__main__":
    unittest.main()
