"""
Comprehensive Integration Tests for the 13 Singularity REST API Endpoints:
- UNIMAX VCD, Quantum Gates, and Ouroboros Zeroize
- Sentinel-RS Bare-Metal Scanner
- DooM Vault 2.0 Ticker, Whale Radar, and Paper Trade
- Mukti Hallucination Insurance Create & Settle
- Vision Liveness & Eye Aspect Ratio
- Full-Duplex Voice & Audio Semaphore
- Nexus Mobile Mainframe Bridge
- IoT Domotics & Focus Controller
"""

import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler


class SingularityEndpointsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token("singularity-test-token")
        cls.token = "singularity-test-token"
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

    # 1. UNIMAX Silicon Endpoints
    def test_unimax_vcd_and_quantum_endpoints(self):
        vcd_res = self._get("/api/unimax/vcd")
        self.assertIn("vcd_trace", vcd_res)
        self.assertIn("$timescale 1ns", vcd_res["vcd_trace"])

        gate_res = self._post("/api/unimax/gate", {"qubit_id": 0, "gate": "H"})
        self.assertEqual(gate_res["num_qubits"], 64)
        self.assertIn("fidelity", gate_res)

        zeroize_res = self._post("/api/unimax/zeroize", {})
        self.assertTrue(zeroize_res["hardware_killswitch_asserted"])

    # 2. Sentinel-RS Endpoint
    def test_sentinel_rs_endpoint(self):
        scan_res = self._post("/api/sentinel/scan", {"host": "127.0.0.1"})
        self.assertEqual(scan_res["target_host"], "127.0.0.1")
        self.assertIsInstance(scan_res["open_ports"], list)

    # 3. DooM Vault 2.0 FinTech Endpoints
    def test_doom_vault_endpoints(self):
        ticker_res = self._get("/api/vault/ticker")
        self.assertIn("BTC", ticker_res["prices"])

        whale_res = self._post("/api/vault/whale", {"symbol": "BTC", "amount_usd": 3000000.0})
        self.assertEqual(whale_res["risk_level"], "MEDIUM")

        trade_res = self._post("/api/vault/trade", {"symbol": "BTC", "action": "BUY", "quantity": 0.1})
        self.assertEqual(trade_res["status"], "FILLED")

    # 4. Mukti Web3 Insurance Endpoints
    def test_mukti_insurance_endpoints(self):
        create_res = self._post("/api/mukti/insurance/create", {
            "client": "0xClientAddress",
            "agent": "0xAgentAddress",
            "code": "def add(x, y): return x + y",
            "stake": 1000.0
        })
        self.assertEqual(create_res["status"], "ACTIVE")
        pol_id = create_res["policy_id"]

        settle_res = self._post("/api/mukti/insurance/settle", {
            "policy_id": pol_id,
            "is_ast_valid": True
        })
        self.assertEqual(settle_res["status"], "BOND_RELEASED_VERIFIED")

    # 5. Vision, Voice, Mobile, and IoT Endpoints
    def test_vision_voice_mobile_iot_endpoints(self):
        vis_res = self._post("/api/vision/liveness", {})
        self.assertTrue(vis_res["is_live_human"])

        voice_res = self._post("/api/voice/duplex", {"audio_energy": 0.8})
        self.assertIn("is_speaking", voice_res)

        mobile_res = self._post("/api/mobile/message", {"chat_id": "100293849", "message": "status"})
        self.assertTrue(mobile_res["success"])
        self.assertIn("CPU", mobile_res["reply_text"])

        iot_res = self._post("/api/iot/focus", {"active": True})
        self.assertTrue(iot_res["is_deep_focus_active"])
        self.assertEqual(iot_res["ambient_color_hex"], "#38bdf8")


if __name__ == "__main__":
    unittest.main()

