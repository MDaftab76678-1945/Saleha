"""Unit tests for Auto-Documentation & Mermaid Diagram Generator."""

import unittest
from saleha.core.autodoc_generator import autodoc_generator


class AutoDocGeneratorTests(unittest.TestCase):

    def test_generate_docs_for_saleha_core(self):
        res = autodoc_generator.generate_docs_for_directory("saleha/harness")
        self.assertTrue(res.total_modules > 0)
        self.assertTrue(res.total_classes > 0)
        self.assertIn("flowchart TD", res.mermaid_diagram)
        self.assertIn("# 📚 Codebase API Documentation", res.markdown_docs)


if __name__ == "__main__":
    unittest.main()

