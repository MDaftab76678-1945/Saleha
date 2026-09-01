"""Unit tests for Web Studio v2.0 API routes and features."""

from __future__ import annotations

import os
import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler


class WebStudioV2Tests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token("studio-v2-test-token")
        cls.token = "studio-v2-test-token"
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str):
        req = urllib.request.Request(
            self.base + path,
            headers={"X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, payload: dict):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_workflow_dag_endpoint(self):
        data = self._get("/api/workflow/dag")
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertTrue(len(data["nodes"]) >= 4)
        node_ids = {n["id"] for n in data["nodes"]}
        self.assertIn("planner", node_ids)
        self.assertIn("coder", node_ids)

    def test_memory_project_endpoint(self):
        data = self._get("/api/memory/project")
        self.assertIn("stats", data)
        self.assertIn("entries", data)

    def test_diff_preview_post_endpoint(self):
        payload = {
            "old_code": "def hello():\n    return 1",
            "new_code": "def hello():\n    return 2",
            "file_path": "test_diff.py"
        }
        data = self._post("/api/diff/preview", payload)
        self.assertEqual(data["file_path"], "test_diff.py")
        self.assertIn("additions", data)
        self.assertIn("deletions", data)
        self.assertIn("risk_score", data)

    def test_voice_dispatch_post_endpoint(self):
        payload = {
            "transcript": "Fix syntax error in auth.py",
            "speak": False
        }
        data = self._post("/api/voice/dispatch", payload)
        self.assertEqual(data["intent"], "FIX")
        self.assertTrue(data["success"])
        self.assertIn("Auto-healing", data["action_summary"])

    def test_browser_preview_post_endpoint(self):
        payload = {
            "html": "<div id='app'>Hello Saleha UI</div>"
        }
        data = self._post("/api/browser/preview", payload)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["viewport_width"], 1280)
        self.assertIn("Hello Saleha UI", data["rendered_preview"])

    def test_project_export_post_endpoint(self):
        import io
        import zipfile
        payload = {
            "files": {
                "index.html": "<h1>Exported</h1>",
                "app.js": "console.log('Exported');"
            }
        }
        req = urllib.request.Request(
            self.base + "/api/project/export",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Content-Type"), "application/zip")
            buf = io.BytesIO(resp.read())
            with zipfile.ZipFile(buf, "r") as zf:
                namelist = zf.namelist()
                self.assertIn("index.html", namelist)
                self.assertIn("app.js", namelist)
                self.assertEqual(zf.read("index.html").decode("utf-8"), "<h1>Exported</h1>")


    def test_workspace_sync_post_endpoint(self):
        import tempfile
        import shutil
        tmp_dir = tempfile.mkdtemp()
        try:
            payload = {
                "directory": tmp_dir,
                "files": {
                    "index.html": "<h1>Synced Disk</h1>",
                    "app.js": "console.log('Synced');"
                }
            }
            data = self._post("/api/workspace/sync", payload)
            self.assertTrue(data["success"])
            self.assertEqual(data["synced_files"], 2)
            with open(os.path.join(tmp_dir, "index.html"), "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "<h1>Synced Disk</h1>")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_ast_merge_post_endpoint(self):
        payload = {
            "ours": "def fn(): return 1",
            "theirs": "def fn2(): return 2"
        }
        data = self._post("/api/ast/merge", payload)
        self.assertTrue(data["success"])
        self.assertTrue(data["ast_valid"])
        self.assertIn("def fn(): return 1", data["merged_code"])
        self.assertIn("def fn2(): return 2", data["merged_code"])


if __name__ == "__main__":
    unittest.main()

