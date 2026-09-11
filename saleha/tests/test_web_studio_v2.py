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
    def setUpClass(cls) -> None:
        web_server.set_auth_token("studio-v2-test-token")
        cls.token = "studio-v2-test-token"
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str) -> None:
        req = urllib.request.Request(
            self.base + path,
            headers={"X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, payload: dict) -> None:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_workflow_dag_endpoint(self) -> None:
        # Node ids/statuses now come from the real, goal-dependent
        # swarm router (route_goal_to_dag) instead of a fixed literal, so
        # this asserts the real contract -- a projected sequence for the
        # default goal, all reported "not_started" since nothing has run --
        # rather than pinning the old hardcoded "planner"/"completed" values.
        data = self._get("/api/workflow/dag")
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertTrue(len(data["nodes"]) >= 4)
        statuses = {n["status"] for n in data["nodes"]}
        self.assertEqual(statuses, {"not_started"})
        node_ids = [n["id"] for n in data["nodes"]]
        self.assertIn("stage_1_architect", node_ids)
        self.assertIn("coder", " ".join(node_ids))

        different = self._get("/api/workflow/dag?goal=Fix%20the%20outage%20traceback")
        self.assertNotEqual(
            [n["id"] for n in different["nodes"]], node_ids,
            "different goals should route to a different stage sequence",
        )

    def test_memory_project_endpoint(self) -> None:
        data = self._get("/api/memory/project")
        self.assertIn("stats", data)
        self.assertIn("entries", data)

    def test_diff_preview_post_endpoint(self) -> None:
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

    def test_voice_dispatch_post_endpoint(self) -> None:
        # This endpoint only classifies intent by keyword match; it does not
        # dispatch to an agent. dispatched must stay False and the response
        # must not claim work happened that never ran.
        payload = {
            "transcript": "Fix syntax error in auth.py",
            "speak": False
        }
        data = self._post("/api/voice/dispatch", payload)
        self.assertEqual(data["intent"], "FIX")
        self.assertFalse(data["dispatched"])
        self.assertIn("note", data)

    def test_browser_preview_post_endpoint(self) -> None:
        payload = {
            "html": "<div id='app'>Hello Saleha UI</div>"
        }
        data = self._post("/api/browser/preview", payload)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["viewport_width"], 1280)
        self.assertIn("Hello Saleha UI", data["rendered_preview"])

    def test_project_export_post_endpoint(self) -> None:
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


    def test_workspace_sync_post_endpoint(self) -> None:
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

    def test_ast_merge_post_endpoint(self) -> None:
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

