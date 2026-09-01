"""Unit tests for Zero-Latency Local Inverted Code Search."""

import unittest
import tempfile
import os
import shutil
from saleha.core.fast_search import FastSearchEngine, SearchMatch


class TestFastSearchEngine(unittest.TestCase):
    """Test suite for FastSearchEngine AST indexing and search query speed."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.tmp_dir, "auth_helper.py")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(
                "class AuthManager:\n"
                "    def authenticate_user(self, username, token):\n"
                "        return True\n"
            )
        self.engine = FastSearchEngine()
        self.engine.index_directory(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_search_finds_indexed_class_and_function(self):
        results = self.engine.search("authenticate_user")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].symbol_name, "authenticate_user")
        self.assertEqual(results[0].symbol_type, "function")

        class_res = self.engine.search("AuthManager")
        self.assertTrue(len(class_res) >= 1)
        self.assertEqual(class_res[0].symbol_name, "AuthManager")
        self.assertEqual(class_res[0].symbol_type, "class")


if __name__ == "__main__":
    unittest.main()
