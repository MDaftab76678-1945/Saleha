"""Unit tests for Interactive Project Onboarding Wizard."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.project_initializer import ProjectInitializer, ProjectInitSummary


class ProjectInitializerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.initializer = ProjectInitializer(root_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_stack_identifies_python(self):
        with open(os.path.join(self.temp_dir, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('hello')\n")
        stack = self.initializer.detect_stack()
        self.assertIn("Python", stack)

    def test_create_saleharules(self):
        rules_p = self.initializer.create_saleharules()
        self.assertTrue(os.path.isfile(rules_p))
        with open(rules_p, "r", encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("Saleha AI Project Architecture Rules", txt)
        self.assertIn("fast_tier", txt)

    def test_initialize_workspace(self):
        summary = self.initializer.initialize_workspace()
        self.assertTrue(summary.success)
        self.assertTrue(os.path.isfile(summary.rules_file_created))


if __name__ == "__main__":
    unittest.main()
