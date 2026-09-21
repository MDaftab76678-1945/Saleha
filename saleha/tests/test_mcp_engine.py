import unittest
import json
from unittest.mock import patch, MagicMock

from saleha.core.mcp_engine import MCPServer, MCPClient


class MCPEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = MCPServer()

    def test_mcp_initialize_handshake(self) -> None:
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

    def test_mcp_tools_list(self) -> None:
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

    def test_mcp_call_tool_sast_scan(self) -> None:
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

    def test_mcp_client_rpc_execution_mock(self) -> None:
        client = MCPClient(command=["echo"])
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}})
            )
            res = client.execute_rpc("initialize")
            self.assertIsNotNone(res)
            self.assertEqual(res["result"]["status"], "ok")

    def test_call_tool_does_not_crash_on_an_unanticipated_exception(self) -> None:
        """Real bug found auditing this module: call_tool only caught
        (TypeError, ValueError, KeyError), so any other exception a handler
        raises -- confirmed by direct probe with a real AttributeError --
        propagated out of call_tool uncaught. An MCP server is a
        long-running process an IDE holds a live connection to; one bad
        tool call must return a clean isError response, not crash the
        whole server for every subsequent request in the session."""
        def broken_handler(args: dict) -> dict:
            raise AttributeError("simulated handler crash")

        self.server.tools["saleha_memory_recall"].handler = broken_handler
        result = self.server.call_tool("saleha_memory_recall", {"query": "x"})
        self.assertTrue(result.get("isError"))
        self.assertIn("simulated handler crash", result["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()

