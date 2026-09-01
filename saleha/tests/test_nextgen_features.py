"""
Unit tests for Saleha Next-Gen Developer Superpowers:
1. Interactive SQL Database Studio (/api/db/query & /api/db/seed)
2. Autonomous GitHub PR Generator (/api/git/pr/generate)
3. In-Browser Sandbox Terminal Shell (/api/terminal/exec)
4. Workspace Direct Disk Sync (/api/workspace/sync)
5. 3-Way Semantic AST Conflict Merger (/api/ast/merge)
"""

import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer
import tempfile
import os
import shutil

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler


class NextGenFeaturesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token("nextgen-test-token")
        cls.token = "nextgen-test-token"
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, path: str, payload: dict):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_sql_query_endpoint(self):
        schema = "CREATE TABLE test_users (id INT, name TEXT); INSERT INTO test_users VALUES (1, 'Alice'), (2, 'Bob');"
        payload = {
            "query": "SELECT * FROM test_users ORDER BY id ASC",
            "schema_sql": schema
        }
        data = self._post("/api/db/query", payload)
        self.assertTrue(data["success"])
        self.assertEqual(data["columns"], ["id", "name"])
        self.assertEqual(len(data["rows"]), 2)
        self.assertEqual(data["rows"][0], [1, "Alice"])

    def test_sql_seed_endpoint(self):
        schema = "CREATE TABLE subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, plan TEXT, mrr_cents INT);"
        payload = {
            "table": "subscriptions",
            "count": 5,
            "schema_sql": schema
        }
        data = self._post("/api/db/seed", payload)
        self.assertTrue(data["success"])
        self.assertEqual(data["inserted_records"], 5)

    def test_git_pr_generate_endpoint(self):
        payload = {
            "files": {
                "index.html": "<h1>Test App</h1>",
                "app.js": "console.log('Test');"
            }
        }
        data = self._post("/api/git/pr/generate", payload)
        self.assertTrue(data["success"])
        self.assertIn("feat(core)", data["pr_title"])
        self.assertIn("Pull Request", data["pr_markdown"])
        self.assertEqual(data["ast_score"], 1.0)

    def test_terminal_exec_endpoint(self):
        payload = {"command": "echo Hello Saleha Terminal"}
        data = self._post("/api/terminal/exec", payload)
        self.assertTrue(data["success"])
        self.assertIn("Hello Saleha Terminal", data["output"])

    def test_terminal_exec_restricted_command(self):
        payload = {"command": "powershell_evil_command"}
        data = self._post("/api/terminal/exec", payload)
        self.assertFalse(data["success"])
        self.assertIn("restricted", data["output"])

    def test_workspace_sync_endpoint(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            payload = {
                "directory": tmp_dir,
                "files": {
                    "server.py": "print('Synced server')",
                    "style.css": "body { background: #000; }"
                }
            }
            data = self._post("/api/workspace/sync", payload)
            self.assertTrue(data["success"])
            self.assertEqual(data["synced_files"], 2)
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, "server.py")))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_ast_merge_endpoint(self):
        payload = {
            "ours": "def local(): return True",
            "theirs": "def remote(): return False"
        }
        data = self._post("/api/ast/merge", payload)
        self.assertTrue(data["success"])
        self.assertTrue(data["ast_valid"])
        self.assertIn("def local(): return True", data["merged_code"])


if __name__ == "__main__":
    unittest.main()
