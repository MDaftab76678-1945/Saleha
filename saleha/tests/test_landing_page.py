"""Unit tests for the Saleha GitHub Pages landing page (docs/index.html).

These assert structure and honesty, not marketing copy. A prior version of
this file pinned fabricated claims in place -- "Devin ($500/mo)" market
comparisons, a SWE-bench leaderboard for a command that was deleted in the
139-command triage, "785 passing tests" -- exactly the trap the audit keeps
finding: a test written against the fake, green forever while the claim is
false. The page was rewritten to carry verified facts only; this file was
rewritten to match.
"""

from __future__ import annotations

import os
import re
import unittest


class LandingPageTests(unittest.TestCase):

    def setUp(self) -> None:
        self.landing_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "docs", "index.html")
        )
        with open(self.landing_path, "r", encoding="utf-8") as f:
            self.content = f.read()
        # Whitespace-collapsed copy, for asserting on phrases that may wrap
        # across lines in the source.
        self.flat = re.sub(r"\s+", " ", self.content)

    def test_landing_page_file_exists(self) -> None:
        self.assertTrue(os.path.isfile(self.landing_path))

    def test_has_core_document_structure(self) -> None:
        self.assertIn("<!DOCTYPE html>", self.content)
        self.assertIn("<title>Saleha", self.content)
        self.assertIn('name="viewport"', self.content)
        self.assertIn('name="description"', self.content)
        self.assertIn('property="og:title"', self.content)
        self.assertIn('property="og:description"', self.content)

    def test_shows_the_real_quickstart(self) -> None:
        # The page teaches the actual install path, not a nonexistent script.
        self.assertIn("pip install -e .", self.content)
        self.assertIn("ollama run", self.content)
        self.assertIn("saleha run", self.content)

    def test_states_verified_numbers_not_fabricated_ones(self) -> None:
        # The numbers on the page must be the ones the repo can back.
        self.assertIn("1,714", self.content)   # real passing-test count
        self.assertIn("156", self.content)     # real registered command count
        # And must NOT carry the claims the audit removed.
        for banned in ("785 passing", "1,004+", "SWE-Bench Verified Leaderboard",
                       "Devin ($500", "Cursor ($20", "CodeRabbit ($12"):
            self.assertNotIn(banned, self.content, f"fabricated claim back on the page: {banned!r}")

    def test_keeps_the_scaffolding_honesty_section(self) -> None:
        # The page must still say plainly what is a template, not a feature.
        self.assertIn("scaffolding, not a finished feature", self.flat)
        self.assertIn("swarm_consensus.py", self.content)
        self.assertIn("formal_verifier.py", self.content)

    def test_measurement_is_presented_with_its_caveat(self) -> None:
        self.assertIn("11 / 12", self.content)
        self.assertIn("10 / 12", self.content)
        self.assertIn("not SWE-bench and not a leaderboard", self.flat)
        self.assertIn("measure_real_pass_rate.py", self.content)

    def test_interactive_pieces_are_present(self) -> None:
        # The 3D hero and scroll-reveal are what "interactive" means here now.
        self.assertIn("bg-canvas", self.content)
        self.assertIn("three.js", self.content.lower())
        self.assertIn("IntersectionObserver", self.content)

    def test_no_decorative_emoji_in_page(self) -> None:
        # Same cp1252 rule as the rest of the repo; the page is plain text.
        emoji = re.findall(r"[\U0001F000-\U0001FAFF☀-➿]", self.content)
        self.assertEqual(emoji, [], f"decorative emoji on the page: {emoji}")


if __name__ == "__main__":
    unittest.main()
