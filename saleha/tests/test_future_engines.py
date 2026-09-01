"""
Unit & Integration tests for Saleha Multi-Horizon Future Engines (Phases 1-4):
1. In-Browser Wasm Runner (Pyodide & QuickJS)
2. Visual Pixel-Diff & Screenshot Regression Verifier
3. P2P Mesh Swarm & Distributed Fuzzing Cluster
4. WebGPU & NPU Local Hardware Accelerators
5. Lean 4 Formal Mathematical Proof Synthesizer
6. Spatial 3D Neural Scene & WebXR Coder
7. NIST Post-Quantum Cryptographic Guard (Kyber & Dilithium)
8. Native Standalone Binary & LLVM Compiler
"""

import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler
from saleha.core.wasm_runner import wasm_engine
from saleha.core.visual_diff import visual_diff_engine
from saleha.core.p2p_swarm import p2p_engine
from saleha.core.webgpu_accelerator import webgpu_accelerator
from saleha.core.formal_verifier import formal_verifier
from saleha.core.spatial_coder import spatial_coder
from saleha.core.pqc_guard import pqc_guard
from saleha.core.native_compiler import native_compiler


class FutureEnginesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        web_server.set_auth_token("future-test-token")
        cls.token = "future-test-token"
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

    # --- Phase 1: Wasm & Visual Diff ---
    def test_wasm_runner_manifest_and_worker(self):
        manifest = wasm_engine.generate_manifest(runtime="pyodide", packages=["numpy"])
        self.assertEqual(manifest.runtime, "pyodide")
        self.assertIn("numpy", manifest.packages)

        script = wasm_engine.generate_worker_script(manifest, code="print('Hello Wasm')")
        self.assertIn("loadPyodide", script)

        data = self._post("/api/wasm/manifest", {"runtime": "pyodide"})
        self.assertEqual(data["runtime"], "pyodide")

    def test_visual_diff_engine_comparison(self):
        base = "<html><body><h1>Title</h1><button>Click</button></body></html>"
        curr = "<html><body><h1>Title</h1><button>Click</button></body></html>"
        res = visual_diff_engine.compare_layouts(base, curr)
        self.assertTrue(res.is_match)
        self.assertGreaterEqual(res.similarity_score, 0.95)

        data = self._post("/api/vision/diff", {"base_html": base, "current_html": curr})
        self.assertTrue(data["is_match"])

    # --- Phase 2: P2P Swarm & WebGPU ---
    def test_p2p_swarm_distributed_fuzzing(self):
        res = p2p_engine.distribute_mutation_fuzzing("def safe(): return 1", total_mutations=200)
        self.assertTrue(res.consensus_achieved)
        self.assertGreaterEqual(res.nodes_participating, 1)

        data = self._post("/api/p2p/fuzz", {"code": "def run(): pass", "mutations": 100})
        self.assertTrue(data["consensus_achieved"])

    def test_webgpu_hardware_acceleration(self):
        rep = webgpu_accelerator.detect_hardware()
        self.assertTrue(rep.webgpu_supported)
        self.assertGreaterEqual(rep.estimated_tokens_per_sec, 50)

        shader = webgpu_accelerator.generate_wgsl_gemm_shader()
        self.assertIn("@compute", shader)

        data = self._get("/api/hardware/accel")
        self.assertTrue(data["webgpu_supported"])

    # --- Phase 3: Formal Verification & Spatial UI ---
    def test_formal_lean4_verifier(self):
        res = formal_verifier.synthesize_proof_for_function("transfer_funds", "def transfer_funds(a, b): pass")
        self.assertTrue(res.is_valid_syntax)
        self.assertIn("Mathlib", res.lean4_code)

        data = self._post("/api/formal/verify", {"function_name": "verify_vault", "code": "def verify(): pass"})
        self.assertTrue(data["is_valid_syntax"])

    def test_spatial_3d_coder(self):
        res = spatial_coder.synthesize_spatial_ui("3D Crypto Dashboard")
        self.assertTrue(res.webxr_ready)
        self.assertIn("Canvas", res.code)

        data = self._post("/api/spatial/generate", {"prompt": "3D Metaverse Hub"})
        self.assertTrue(data["webxr_ready"])

    # --- Phase 4: Post-Quantum Cryptography & Native Compiler ---
    def test_post_quantum_cryptography_kyber(self):
        kp = pqc_guard.generate_kyber_keypair()
        self.assertEqual(kp.algorithm, "CRYSTALS-Kyber-1024")

        enc = pqc_guard.encrypt_quantum_safe("TopSecretKey123", kp.public_key_b64)
        self.assertIn("Kyber", enc.algorithm)
        self.assertIsNotNone(enc.ciphertext_b64)

        data = self._post("/api/pqc/encrypt", {"plaintext": "QuantumSafePassword"})
        self.assertIn("Kyber", data["algorithm"])

    def test_native_binary_compiler(self):
        c_code = "#include <stdio.h>\nint main() { printf(\"Saleha Native\"); return 0; }\n"
        res = native_compiler.compile_c_standalone(c_code, binary_name="test_native_app")
        self.assertTrue(res.success)
        self.assertGreater(res.binary_size_bytes, 0)

        data = self._post("/api/native/compile", {"code": c_code, "binary_name": "api_test_app"})
        self.assertTrue(data["success"])


if __name__ == "__main__":
    unittest.main()

