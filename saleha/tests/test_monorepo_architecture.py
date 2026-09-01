"""
Unit & Architecture tests for Saleha Ecosystem & Architecture.
Verifies core product architecture, design standards, and CI pipelines.
"""

import os
import json
import unittest
from pathlib import Path


class MonorepoArchitectureTests(unittest.TestCase):

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parents[2]

    def test_phase0_product_brief_exists_and_complete(self):
        brief_path = self.root_dir / "PRODUCT_BRIEF.md"
        self.assertTrue(brief_path.exists())
        content = brief_path.read_text(encoding="utf-8")
        self.assertIn("Saleha AI", content)
        self.assertIn("Zero-leak", content)
        self.assertIn("LOOP_CHECK", content)

    def test_architecture_documentation_exists(self):
        arch_path = self.root_dir / "ARCHITECTURE.md"
        self.assertTrue(arch_path.exists())
        content = arch_path.read_text(encoding="utf-8")
        self.assertIn("Saleha", content)

    def test_roadmap_documentation_exists(self):
        roadmap_path = self.root_dir / "ROADMAP.md"
        self.assertTrue(roadmap_path.exists())
        content = roadmap_path.read_text(encoding="utf-8")
        self.assertIn("Saleha", content)

    def test_github_actions_ci_workflow_configured(self):
        ci_yml = self.root_dir / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_yml.exists())
        ci_text = ci_yml.read_text(encoding="utf-8")
        self.assertIn("pytest saleha/tests/", ci_text)
        self.assertIn("build_extension.py", ci_text)

    def test_optional_turborepo_configuration(self):
        turbo_path = self.root_dir / "turbo.json"
        if turbo_path.exists():
            with open(turbo_path, "r", encoding="utf-8") as f:
                turbo_cfg = json.load(f)
            self.assertIn("tasks", turbo_cfg)


if __name__ == "__main__":
    unittest.main()
