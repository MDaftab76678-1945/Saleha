"""Unit tests for Standard JSON-RPC LSP Daemon."""

from __future__ import annotations

import unittest
from saleha.core.lsp_server import SalehaLSPServer


class LSPServerTests(unittest.TestCase):

    def setUp(self):
        self.server = SalehaLSPServer(root_dir=".")

    def test_initialize_request(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"rootUri": "file:///workspace"}
        }
        res = self.server.handle_request(req)
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 1)
        self.assertTrue(res["result"]["capabilities"]["definitionProvider"])
        self.assertTrue(self.server.is_initialized)

    def test_did_open_generates_diagnostics(self):
        # Valid code
        req = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "file:///test.py",
                    "text": "def valid_func():\n    return 42\n"
                }
            }
        }
        res = self.server.handle_request(req)
        self.assertEqual(res["method"], "textDocument/publishDiagnostics")
        self.assertEqual(len(res["params"]["diagnostics"]), 0)

        # Invalid syntax code
        req_invalid = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "file:///broken.py",
                    "text": "def broken_func( ::::"
                }
            }
        }
        res_invalid = self.server.handle_request(req_invalid)
        self.assertEqual(len(res_invalid["params"]["diagnostics"]), 1)
        self.assertEqual(res_invalid["params"]["diagnostics"][0]["severity"], 1)

    def test_completion_request(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/completion",
            "params": {}
        }
        res = self.server.handle_request(req)
        self.assertIsNotNone(res)
        self.assertIn("items", res["result"])


if __name__ == "__main__":
    unittest.main()

