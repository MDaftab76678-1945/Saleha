"""Unit tests for Offline Doc Researcher & API Signature Injector."""

import unittest
from saleha.core.doc_researcher import DocResearcher


class DocResearcherTests(unittest.TestCase):

    def setUp(self):
        self.researcher = DocResearcher()

    def test_lookup_fastapi_signature(self):
        sig = self.researcher.lookup("fastapi", "FastAPI")
        self.assertIsNotNone(sig)
        self.assertEqual(sig.package, "fastapi")
        self.assertIn("title", sig.signature)

    def test_lookup_pydantic_signature(self):
        sig = self.researcher.lookup("pydantic", "BaseModel")
        self.assertIsNotNone(sig)
        self.assertEqual(sig.symbol, "BaseModel")

    def test_search_docs_returns_matches(self):
        matches = self.researcher.search_docs("requests")
        self.assertTrue(len(matches) >= 2)

    def test_inject_context_for_prompt(self):
        prompt = "Create a FastAPI backend with Pydantic validation models"
        injected = self.researcher.inject_context_for_prompt(prompt)
        self.assertIn("Verified API Signatures", injected)
        self.assertIn("fastapi", injected.lower())


if __name__ == "__main__":
    unittest.main()

