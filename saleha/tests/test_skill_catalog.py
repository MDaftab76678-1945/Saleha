"""
Unit & Integration Tests for Saleha 1,000+ AgentSkills Engine & Universal Catalog.
"""

from __future__ import annotations

import unittest
from saleha.core.skill_catalog import SkillCatalog, AgentSkillMetadata, skill_catalog


class SkillCatalogTests(unittest.TestCase):

    def setUp(self):
        self.catalog = skill_catalog

    def test_catalog_exceeds_1000_skills(self):
        stats = self.catalog.get_stats()
        self.assertGreaterEqual(stats["total_skills"], 1000)
        self.assertEqual(stats["total_domains"], 25)
        self.assertGreater(stats["total_indexed_keywords"], 1500)

    def test_domain_distribution_balance(self):
        stats = self.catalog.get_stats()
        for domain in SkillCatalog.DOMAINS:
            count = stats["domain_breakdown"].get(domain, 0)
            self.assertGreaterEqual(count, 35, f"Domain {domain} has insufficient skills: {count}")

    def test_search_skills_precision(self):
        k8s_matches = self.catalog.search_skills("kubernetes", limit=10)
        self.assertTrue(len(k8s_matches) > 0)
        self.assertTrue(any("k8s" in s.name or "kubernetes" in s.name or "kubernetes" in s.trigger_keywords for s in k8s_matches))

        react_matches = self.catalog.search_skills("react", domain="frontend_web", limit=5)
        self.assertTrue(len(react_matches) > 0)
        for s in react_matches:
            self.assertEqual(s.domain, "frontend_web")

    def test_skill_markdown_specification(self):
        skill = self.catalog.get_skill("react-component-scaffold")
        self.assertIsNotNone(skill)
        md = skill.to_markdown()
        self.assertIn("---", md)
        self.assertIn("domain: frontend_web", md)
        self.assertIn("Input Schema", md)
        self.assertIn("Output Schema", md)

    def test_execute_skill(self):
        res = self.catalog.execute_skill("fastapi-crud-router", {"task": "Create /users router"})
        self.assertTrue(res["success"])
        self.assertEqual(res["domain"], "backend_microservices")
        self.assertEqual(res["skill"], "fastapi-crud-router")


if __name__ == "__main__":
    unittest.main()
