"""Unit tests for Saleha AI Product Landing Page."""

from __future__ import annotations

import os
import unittest


class LandingPageTests(unittest.TestCase):

    def setUp(self):
        self.landing_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "index.html"))

    def test_landing_page_file_exists(self):
        self.assertTrue(os.path.isfile(self.landing_path), f"Landing page missing at: {self.landing_path}")

    def test_landing_page_contains_crucial_seo_tags(self):
        with open(self.landing_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("<title>Saleha AI", content)
        self.assertIn("name=\"viewport\"", content)
        self.assertIn("name=\"description\"", content)
        self.assertIn("property=\"og:title\"", content)
        self.assertIn("property=\"og:description\"", content)

    def test_landing_page_contains_install_commands(self):
        with open(self.landing_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Unix install
        self.assertIn("install.sh", content)
        # Windows install
        self.assertIn("install.ps1", content)

    def test_landing_page_contains_all_superpowers(self):
        with open(self.landing_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Autonomous Self-Healing Loop", content)
        self.assertIn("AI Deep Code Reviewer", content)
        self.assertIn("Per-Project Episodic Memory", content)
        self.assertIn("Local LoRA Fine-Tuning", content)
        self.assertIn("Surgical Diff &amp; Blast Radius", content)
        self.assertIn("Real-Time Watch-AI Suggester", content)

    def test_landing_page_contains_market_comparison(self):
        with open(self.landing_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Devin ($500/mo)", content)
        self.assertIn("Cursor ($20/mo)", content)
        self.assertIn("CodeRabbit ($12/mo)", content)
        self.assertIn("calc-slider", content)

    def test_landing_page_contains_interactive_scripts(self):
        with open(self.landing_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("function switchInstall", content)
        self.assertIn("function copyInstall", content)
        self.assertIn("function updateSavings", content)
        self.assertIn("function switchCliTab", content)


if __name__ == "__main__":
    unittest.main()

