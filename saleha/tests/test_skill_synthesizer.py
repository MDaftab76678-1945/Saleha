"""Unit tests for Dynamic Skill Synthesizer & Continuous Learning Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from saleha.core.skill_synthesizer import SkillSynthesizer, SynthesizedSkill
from saleha.agents.base_agent import AgentResponse


class SkillSynthesizerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.synthesizer = SkillSynthesizer(skills_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_distill_from_execution_generates_skill(self):
        with patch.object(self.synthesizer.agent, "think") as mock_think:
            mock_think.return_value = AgentResponse(
                success=True,
                content="""---
name: postgres_connection_pool_tuning
description: Tune PostgreSQL max_connections and pool size
triggers:
  - "postgres connection pool"
---

# PostgreSQL Connection Pool Tuning
1. Adjust pool_size to 20.
2. Enable keepalives.
"""
            )
            skill = self.synthesizer.distill_from_execution(
                task_goal="Tune PostgreSQL connection pool",
                execution_trace="Executed vacuum and pool adjustments",
                skill_name="postgres_pool_tuning"
            )
            self.assertEqual(skill.name, "postgres_pool_tuning")
            self.assertIn("PostgreSQL", skill.markdown_content)

    def test_save_skill_persists_to_disk_and_registry(self):
        skill = SynthesizedSkill(
            name="docker_multistage_cache",
            description="Optimize Docker cache layering",
            triggers=["docker build cache"],
            markdown_content="# Docker Multistage Cache\nUse --cache-from."
        )
        saved_file = self.synthesizer.save_skill(skill, custom_dir=self.temp_dir)
        self.assertTrue(os.path.isfile(saved_file))
        with open(saved_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Docker Multistage Cache", content)


if __name__ == "__main__":
    unittest.main()

