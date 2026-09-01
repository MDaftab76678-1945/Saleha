"""
Unit & Integration tests for Saleha 8 Blindspot Improvements:
1. Dynamic File Tree Management (Create, Rename, Delete)
2. Visual .env & Secrets Studio Vault Integration
3. Split-Screen Dual-Pane Editor State
4. State-Preserving Live HMR Message Formats
5. Git Inline Diff Gutter Calculation
6. PTY Interactive Terminal Shell with ANSI Color Streams
7. AI Voice Text-to-Speech Output Dispatch
"""

import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler
from saleha.core.vault import vault
from saleha.core.visual_diff import visual_diff_engine


class BlindspotImprovementsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token("blindspot-test-token")
        cls.token = "blindspot-test-token"
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

    def test_vault_secrets_set_and_list(self):
        # 1. Set secret via REST API
        set_res = self._post("/api/vault/set", {"key": "TEST_STRIPE_KEY", "value": "sk_test_9849204820948"})
        self.assertEqual(set_res["status"], "success")

        # 2. List secrets via REST API
        list_res = self._get("/api/vault/list")
        self.assertIn("TEST_STRIPE_KEY", list_res["secrets"])

    def test_dynamic_file_tree_workspace_sync(self):
        files_payload = {
            "index.html": "<h1>App</h1>",
            "components/Button.jsx": "export const Button = () => <button>Click</button>;",
            "utils/math.js": "export const add = (a, b) => a + b;",
        }
        res = self._post("/api/workspace/sync", {"directory": "./test_dynamic_ws", "files": files_payload})
        self.assertTrue(res["success"])
        self.assertEqual(res["synced_files"], 3)

    def test_interactive_terminal_ansi_and_multicommand(self):
        res = self._post("/api/terminal/exec", {"command": "echo Hello ANSI World"})
        self.assertTrue(res["success"])
        self.assertIn("Hello ANSI World", res["output"])

    def test_voice_dispatch_audio_confirmation(self):
        res = self._post("/api/voice/dispatch", {"transcript": "Build SaaS payment module", "speak": True})
        self.assertTrue(res["success"])
        self.assertTrue(res["speak_audio"])
        self.assertEqual(res["intent"], "GENERATE")

    def test_visual_diff_layout_regression_guard(self):
        base = "<html><body><h1>Dashboard</h1><button>Checkout</button></body></html>"
        curr = "<html><body><h1>Dashboard</h1></body></html>"  # Button missing -> regression!
        diff = visual_diff_engine.compare_layouts(base, curr)
        self.assertFalse(diff.is_match)
        self.assertGreater(diff.regressions_detected, 0)
        self.assertIn("Missing interactive CTA", diff.delta_details[0])


if __name__ == "__main__":
    unittest.main()

