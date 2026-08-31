"""Unit tests for Automated Static Documentation Site Generator."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.docs_generator import DocsGenerator


class DocsGeneratorTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.generator = DocsGenerator(root_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_html_docs_contains_key_elements(self):
        html = self.generator.generate_html_docs()
        self.assertIn("Saleha AI Documentation", html)
        self.assertIn("Quick Start CLI Commands", html)
        self.assertIn("Multi-Agent Swarm Personas", html)

    def test_build_docs_site(self):
        out_p = os.path.join(self.temp_dir, "site", "index.html")
        saved = self.generator.build_docs_site(output_path=out_p)
        self.assertTrue(os.path.isfile(saved))


if __name__ == "__main__":
    unittest.main()

