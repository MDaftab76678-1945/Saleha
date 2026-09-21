"""
Unit & Integration Tests for Saleha Universal Model Context Protocol (MCP) Multi-Platform Hub.
"""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from unittest.mock import patch
from saleha.core.mcp_hub import UniversalMCPHub, MCPServerConfig, mcp_hub


class MCPHubTests(unittest.TestCase):

    def setUp(self) -> None:
        self.hub = mcp_hub

    def test_hub_has_over_25_builtin_servers(self) -> None:
        servers = self.hub.list_servers()
        self.assertGreaterEqual(len(servers), 25)

    def test_export_claude_desktop_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "claude_desktop_config.json")
            target_file, config_data = self.hub.export_config("claude", output_path=out_file)
            self.assertTrue(os.path.isfile(target_file))
            self.assertIn("mcpServers", config_data)
            self.assertIn("filesystem", config_data["mcpServers"])
            self.assertIn("github", config_data["mcpServers"])
            self.assertIn("saleha", config_data["mcpServers"])

    def test_export_cursor_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, ".cursor", "mcp.json")
            target_file, config_data = self.hub.export_config("cursor", output_path=out_file)
            self.assertTrue(os.path.isfile(target_file))
            self.assertIn("mcpServers", config_data)

    def test_export_zed_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "zed_settings.json")
            target_file, config_data = self.hub.export_config("zed", output_path=out_file)
            self.assertTrue(os.path.isfile(target_file))
            self.assertIn("context_servers", config_data)
            self.assertIn("command", config_data["context_servers"]["filesystem"])

    def test_connect_server_with_resolvable_command_reports_command_resolved(self) -> None:
        with patch("saleha.core.mcp_hub.shutil.which", return_value="/usr/bin/npx"):
            res = self.hub.connect_server("filesystem")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "command_resolved")
        self.assertEqual(res["server"], "filesystem")

    def test_connect_server_with_missing_command_reports_failure_not_success(self) -> None:
        """Real bug found auditing this module: connect_server()'s own
        comment said "Simulated successful handshake" and it unconditionally
        returned success=True/status=connected for any registered server,
        with zero process spawned. Confirmed live: connect_server('postgres')
        reported a green "Successfully initialized MCP connection" with no
        Postgres instance running anywhere -- and the real CLI caller
        (`saleha mcp connect`) surfaces that straight to the user. Must now
        genuinely check whether the launch command resolves, and report
        failure honestly when it doesn't."""
        with patch("saleha.core.mcp_hub.shutil.which", return_value=None):
            res = self.hub.connect_server("postgres")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "command_not_found")

    def test_connect_unknown_server_reports_not_found(self) -> None:
        res = self.hub.connect_server("nonexistent_server_xyz")
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"])


if __name__ == "__main__":
    unittest.main()
