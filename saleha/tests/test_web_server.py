import unittest
import threading
import json
import urllib.request
import urllib.error
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler


AUTH_TOKEN = "test-suite-token"


class WebServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token(AUTH_TOKEN)
        # Bind to port 0 to let OS assign an available port
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str, auth: bool = True) -> tuple[int, bytes]:
        headers = {"X-Saleha-Token": AUTH_TOKEN} if auth else {}
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()

    def _post(self, path: str, payload: dict, auth: bool = True) -> tuple[int, bytes]:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["X-Saleha-Token"] = AUTH_TOKEN
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()

    def _get_status_only(self, path: str, headers: dict | None = None) -> int:
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status
        except urllib.error.HTTPError as err:
            return err.code

    # ---------------- Security posture tests ----------------

    def test_api_requires_token(self):
        self.assertEqual(self._get_status_only("/api/status"), 401)

    def test_api_rejects_wrong_token(self):
        self.assertEqual(
            self._get_status_only("/api/status", {"X-Saleha-Token": "wrong-token"}),
            401,
        )

    def test_api_rejects_bad_query_token(self):
        self.assertEqual(self._get_status_only("/api/status?token=nope"), 401)

    def test_index_page_served_without_token_and_injects_token(self):
        status, body = self._get("/", auth=False)
        self.assertEqual(status, 200)
        self.assertIn(AUTH_TOKEN.encode(), body)

    def test_no_wildcard_cors_header_on_json_responses(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/status",
            headers={"X-Saleha-Token": AUTH_TOKEN}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertIsNone(resp.headers.get("Access-Control-Allow-Origin"))

    def test_post_without_token_is_unauthorized(self):
        data = json.dumps({"code": "print('x')"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/exec",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as err:
            status = err.code
        self.assertEqual(status, 401)

    # ---------------- Functional tests ----------------

    def test_get_index_html(self):
        status, body = self._get("/", auth=False)
        self.assertEqual(status, 200)
        self.assertIn(b"Saleha AI Web Studio", body)

    def test_get_api_status(self):
        status, body = self._get("/api/status")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "healthy")
        self.assertGreaterEqual(data["agent_profiles_count"], 1)

    def test_get_api_agents(self):
        status, body = self._get("/api/agents")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("profiles", data)
        self.assertGreaterEqual(len(data["profiles"]), 1)

    def test_get_api_tools(self):
        status, body = self._get("/api/tools")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("tools", data)
        tool_names = [t["name"] for t in data["tools"]]
        self.assertIn("web_fetch", tool_names)

    def test_get_api_memory(self):
        status, body = self._get("/api/memory")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("total_entries", data)

    def test_post_api_scan(self):
        status, body = self._post("/api/scan", {"path": "."})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("summary", data)
        self.assertGreater(data["summary"]["total_files"], 0)

    def test_post_api_exec(self):
        status, body = self._post("/api/exec", {"language": "python", "code": "print('hello_sandbox')"})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("hello_sandbox", data["output"])

    def test_post_api_vision(self):
        status, body = self._post("/api/vision/generate", {"spec": "Button with icon", "framework": "react"})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["framework"], "react")
        self.assertTrue(len(data["code"]) > 10)

    def test_post_api_fuzz(self):
        status, body = self._post("/api/fuzz/run", {"code": "def handle(v): return len(str(v))"})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["total_mutations"], 4)

    def test_post_api_sre(self):
        status, body = self._post("/api/sre/analyze", {"log": "ZeroDivisionError: division by zero"})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["error_type"], "ZeroDivisionError")
        self.assertIn("denominator == 0", data["hotfix"])

    def test_post_api_deploy(self):
        status, body = self._post("/api/deploy/generate", {"app_name": "demo-svc", "port": 8000})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["app_name"], "demo-svc")
        self.assertIn("FROM python", data["dockerfile"])

    def test_post_api_loadtest(self):
        status, body = self._post("/api/loadtest/run", {"url": f"{self.base_url}/api/status", "requests": 10})
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["rps"] > 0)


if __name__ == "__main__":
    unittest.main()
