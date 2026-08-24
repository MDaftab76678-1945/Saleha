import unittest
import json
from unittest.mock import patch, MagicMock

from saleha.core.mcp_engine import MCPServer, MCPClient


class MCPEngineTests(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer()

    def test_mcp_initialize_handshake(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        res = self.server.handle_json_rpc(req)
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 1)
        self.assertIn("serverInfo", res["result"])
        self.assertEqual(res["result"]["serverInfo"]["name"], "saleha-ai-server")

    def test_mcp_tools_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        res = self.server.handle_json_rpc(req)
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("saleha_team_swarm", tool_names)
        self.assertIn("saleha_dag_execute", tool_names)
        self.assertIn("saleha_sast_scan", tool_names)
        self.assertIn("saleha_sandbox_run", tool_names)
        self.assertIn("saleha_memory_recall", tool_names)

    def test_mcp_call_tool_sast_scan(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "saleha_sast_scan",
                "arguments": {"path": "."}
            }
        }
        with patch.object(self.server, "_handle_sast_scan", return_value={"total_files": 10, "high": 0}):
            res = self.server.handle_json_rpc(req)
            self.assertEqual(res["id"], 3)
            self.assertIn("content", res["result"])
            self.assertIn("total_files", res["result"]["content"][0]["text"])

    def test_mcp_client_rpc_execution_mock(self):
        client = MCPClient(command=["echo"])
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}})
            )
            res = client.execute_rpc("initialize")
            self.assertIsNotNone(res)
            self.assertEqual(res["result"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()

