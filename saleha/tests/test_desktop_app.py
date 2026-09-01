"""Unit tests for Saleha Desktop GUI Application & Local LLM Manager."""

from __future__ import annotations

import os
import json
import unittest
import urllib.request
from unittest.mock import patch, MagicMock

from saleha.desktop.app import SalehaDesktopApp, LocalLLMManager, LocalLLMStatus
from scripts.package_desktop_app import generate_desktop_manifest


class DesktopAppTests(unittest.TestCase):

    def setUp(self):
        self.app = SalehaDesktopApp(port=0)
        self.llm_manager = LocalLLMManager()

    def tearDown(self):
        self.app.stop()

    def test_start_server_assigns_port_and_serves_status(self):
        assigned_port = self.app.start_server()
        self.assertGreater(assigned_port, 1024)
        self.assertTrue(self.app.is_running)

        url = f"http://127.0.0.1:{assigned_port}/api/desktop/status"
        req = urllib.request.Request(url, headers={"X-Saleha-Token": self.app.token})
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("version", data)
            self.assertIn("llm_status", data)
            self.assertIn("agents_count", data)

    def test_local_llm_manager_fallback_status(self):
        # When Ollama is offline or unavailable
        status: LocalLLMStatus = self.llm_manager.check_status()
        self.assertIsInstance(status.is_running, bool)
        self.assertIn("http://localhost:11434", status.server_url)

    def test_generate_desktop_manifest(self):
        manifest_path = generate_desktop_manifest(output_dir="dist/desktop_test")
        self.assertTrue(os.path.isfile(manifest_path))

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["name"], "Saleha AI Desktop")
            self.assertEqual(data["version"], "2.0.0")
            self.assertTrue(data["features"]["dag_visualizer"])

        # Clean up test dir
        import shutil
        shutil.rmtree("dist/desktop_test", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
