"""Unit tests for Graph RAG & Natural Language Codebase Q&A Engine."""

import unittest
from saleha.core.graph_rag import graph_rag


class GraphRAGTests(unittest.TestCase):

    def test_graph_rag_query(self):
        ans = graph_rag.query("How does security scanner detect vulnerabilities?", root_dir="saleha")
        self.assertEqual(ans.question, "How does security scanner detect vulnerabilities?")
        self.assertTrue(len(ans.answer) > 20)
        self.assertTrue(isinstance(ans.relevant_files, list))


if __name__ == "__main__":
    unittest.main()

