"""
Integration tests for Saleha Web Studio Master Vision REST & SSE endpoints:
1. POST /api/octopus/run
2. GET /api/stream/octopus
3. POST /api/supremacy/run
4. POST /api/solve/run
5. POST /api/tools/forge
"""

from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer
from unittest.mock import patch

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler

AUTH_TOKEN = "tok-" + uuid.uuid4().hex[:16]


class MasterVisionWebServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        web_server.set_auth_token(AUTH_TOKEN)
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    REQUEST_TIMEOUT = 30

    def _get(self, path: str, auth: bool = True) -> tuple[int, bytes, dict]:
        headers = {"X-Saleha-Token": AUTH_TOKEN} if auth else {}
        req = urllib.request.Request(f"{self.base_url}{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT) as resp:
            return resp.status, resp.read(), dict(resp.headers)

    def _post(self, path: str, payload: dict, auth: bool = True) -> tuple[int, bytes]:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["X-Saleha-Token"] = AUTH_TOKEN
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT) as resp:
            return resp.status, resp.read()

    def test_unauthorized_access_rejected(self) -> None:
        """Endpoints under /api/ reject missing auth token with HTTP 401."""
        req = urllib.request.Request(f"{self.base_url}/api/octopus/run", data=b"{}", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=self.REQUEST_TIMEOUT)
        self.assertEqual(ctx.exception.code, 401)

    def test_post_octopus_run(self) -> None:
        """POST /api/octopus/run executes coordinate and returns comprehensive payload."""
        status, body = self._post(
            "/api/octopus/run",
            {
                "goal": "Build an ultra-fast token bucket limiter",
                "model": "mock",
                "supremacy": True,
                "timeout": 30.0,
            },
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("execution_id", data)
        self.assertEqual(data["goal"], "Build an ultra-fast token bucket limiter")
        self.assertIn("brain_outputs", data)
        self.assertIn("coder", data["brain_outputs"])
        self.assertEqual(data["brain_outputs"]["coder"]["status"], "success")
        self.assertIn("Local Supremacy", data["brain_outputs"]["coder"]["summary"])

    def test_get_stream_octopus_sse(self) -> None:
        """GET /api/stream/octopus returns text/event-stream with live brain dispatches."""
        status, body, headers = self._get(
            "/api/stream/octopus?goal=Stream+Limiter&model=mock&supremacy=true"
        )
        self.assertEqual(status, 200)
        content_type = headers.get("Content-Type", "")
        self.assertIn("text/event-stream", content_type)
        raw_text = body.decode("utf-8")
        self.assertIn("data: {", raw_text)
        self.assertIn('"brain_output"', raw_text)
        self.assertIn('"complete"', raw_text)

    def test_post_supremacy_run(self) -> None:
        """POST /api/supremacy/run executes LocalSupremacy tournament."""
        status, body = self._post(
            "/api/supremacy/run",
            {
                "problem": "def solve(n):\n    return n * 2",
                "test_suite": "assert solve(2) == 4",
                "model": "mock",
                "num_trajectories": 4,
            },
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("winner_code", data)
        self.assertIn("winner_strategy", data)
        self.assertIn("amplification_factor", data)
        self.assertIn("total_candidates", data)

    def test_post_solve_run(self) -> None:
        """POST /api/solve/run triggers autonomous IssueResolver."""
        from saleha.core.diff_engine import DiffHunk, DiffResult

        fake_diff = DiffResult(
            file_path="service.py",
            old_content="def run(): return 1",
            new_content="def run(): return 2",
            hunks=[DiffHunk(hunk_id=1, old_start=1, old_lines=["def run(): return 1"], new_start=1, new_lines=["def run(): return 2"])],
            risk_score=1,
            risk_reason="Low risk fix",
            lines_added=1,
            lines_removed=1,
            unified_diff="--- a/service.py\n+++ b/service.py\n@@ -1 +1 @@\n-def run(): return 1\n+def run(): return 2",
        )

        with patch("saleha.core.issue_resolver.IssueResolver._run_agent_solver", return_value=fake_diff), \
             patch("saleha.core.issue_resolver.IssueResolver.create_fix_branch", return_value=("fix/test-branch", "")):
            status, body = self._post(
                "/api/solve/run",
                {
                    "issue_ref": "Resolve NullPointerException in rate limiter",
                    "model": "mock",
                    "autonomous": True,
                },
            )
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["success"])
            self.assertEqual(data["branch_name"], "fix/test-branch")
            self.assertIn("service.py", data["diff"])

    def test_post_tools_forge(self) -> None:
        """POST /api/tools/forge synthesizes and registers tools."""
        from saleha.core.tool_forge import ToolForgeResult

        fake_forge_res = ToolForgeResult(
            timestamp="2026-09-21 00:00:00",
            tool_name="metric_calculator",
            status="created",
            detail="Synthesized and verified metric_calculator tool",
            tool_path="saleha/tools/metric_calculator.py",
            test_path="saleha/tests/test_tool_metric_calculator.py",
            quality_score=9.5,
            tests_passed=True,
        )

        with patch("saleha.core.tool_forge.ToolForge.forge_tool", return_value=fake_forge_res):
            status, body = self._post(
                "/api/tools/forge",
                {
                    "name": "metric_calculator",
                    "description": "Calculates algorithmic efficiency metrics",
                    "parameters": {"type": "object", "properties": {"x": {"type": "number"}}},
                },
            )
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertEqual(data["tool_name"], "metric_calculator")
            self.assertEqual(data["status"], "created")
            self.assertTrue(data["tests_passed"])


if __name__ == "__main__":
    unittest.main()
