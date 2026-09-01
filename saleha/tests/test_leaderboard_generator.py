"""Unit tests for SWE-Bench Public Leaderboard Generator."""

import unittest
from saleha.core.leaderboard_generator import LeaderboardGenerator, PlatformBenchmarkScore


class TestLeaderboardGenerator(unittest.TestCase):
    """Test suite for LeaderboardGenerator markdown and HTML rendering."""

    def setUp(self):
        self.generator = LeaderboardGenerator()

    def test_generate_markdown_contains_platforms(self):
        md = self.generator.generate_markdown()
        self.assertIn("Saleha v2.6.0", md)
        self.assertIn("Devin", md)
        self.assertIn("Claude Code", md)
        self.assertIn("100% Local", md)

    def test_generate_html_contains_valid_table(self):
        html = self.generator.generate_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Global AI Software Engineering Leaderboard", html)
        self.assertIn("<table>", html)


if __name__ == "__main__":
    unittest.main()
