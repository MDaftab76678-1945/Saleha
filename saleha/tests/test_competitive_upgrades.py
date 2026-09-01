"""
Unit & Integration tests for Saleha 5 Competitive Upgrades:
1. Visual Time-Travel History & Rewind Buffer (v0 / Devin Style)
2. Top-Bar Multi-Model Live Switcher (Cursor / Windsurf Style)
3. 50+ Modular UI Component Blocks Gallery Drawer (v0 Style)
4. 1-Click Cloud & GitHub Deployer Modal (Bolt.new / Lovable Style)
5. In-Browser Virtual ES Module & Package Importer (Bolt.new Style)
"""

import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler
from saleha.core.vision_coder import vision_coder


class CompetitiveUpgradesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token("competitive-test-token")
        cls.token = "competitive-test-token"
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

    def _get(self, path: str):
        req = urllib.request.Request(
            self.base + path,
            headers={"X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_model_selector_routing_support(self):
        # Verify vision synthesis supports passing specific frontier reasoning models
        res = self._post("/api/vision/generate", {
            "prompt": "Modern SaaS Pricing Table",
            "framework": "html",
            "model": "deepseek-r1",
            "use_llm": False,
        })
        self.assertEqual(res["framework"], "html")
        self.assertIsNotNone(res["component_name"])
        self.assertIsNotNone(res["code"])

    def test_cloud_deployer_manifest_synthesis(self):
        # 1-Click deploy package generation
        res = self._post("/api/deploy/generate", {
            "app_name": "saleha-prod-store",
            "port": 3000,
        })
        self.assertEqual(res["app_name"], "saleha-prod-store")
        self.assertIn("FROM python", res["dockerfile"])
        self.assertIn("kind: Deployment", res["k8s_manifest"])

    def test_github_pr_generator_workflow(self):
        files = {
            "index.html": "<html><body><h1>Saleha</h1></body></html>",
            "server.py": "from fastapi import FastAPI\napp = FastAPI()",
        }
        res = self._post("/api/git/pr/generate", {"files": files})
        self.assertTrue(res["success"])
        self.assertIn("Pull Request", res["pr_markdown"])
        self.assertEqual(res["ast_score"], 1.0)


if __name__ == "__main__":
    unittest.main()

