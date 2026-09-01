"""
Unit & Integration Tests for Saleha Universal Model Context Protocol (MCP) Multi-Platform Hub.
"""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from saleha.core.mcp_hub import UniversalMCPHub, MCPServerConfig, mcp_hub


class MCPHubTests(unittest.TestCase):

    def setUp(self):
        self.hub = mcp_hub

    def test_hub_has_over_25_builtin_servers(self):
        servers = self.hub.list_servers()
        self.assertGreaterEqual(len(servers), 25)

    def test_export_claude_desktop_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "claude_desktop_config.json")
            target_file, config_data = self.hub.export_config("claude", output_path=out_file)
            self.assertTrue(os.path.isfile(target_file))
            self.assertIn("mcpServers", config_data)
            self.assertIn("filesystem", config_data["mcpServers"])
            self.assertIn("github", config_data["mcpServers"])
            self.assertIn("saleha", config_data["mcpServers"])

    def test_export_cursor_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, ".cursor", "mcp.json")
            target_file, config_data = self.hub.export_config("cursor", output_path=out_file)
            self.assertTrue(os.path.isfile(target_file))
            self.assertIn("mcpServers", config_data)

    def test_export_zed_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "zed_settings.json")
            target_file, config_data = self.hub.export_config("zed", output_path=out_file)
            self.assertTrue(os.path.isfile(target_file))
            self.assertIn("context_servers", config_data)
            self.assertIn("command", config_data["context_servers"]["filesystem"])

    def test_connect_mcp_server(self):
        res = self.hub.connect_server("filesystem")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "connected")
        self.assertEqual(res["server"], "filesystem")


if __name__ == "__main__":
    unittest.main()
