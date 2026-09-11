"""
Unit & Integration tests for Saleha Multi-Horizon Future Engines (Phases 1-4):
1. In-Browser Wasm Runner (Pyodide & QuickJS)
2. Visual Pixel-Diff & Screenshot Regression Verifier
3. P2P Mesh Swarm & Distributed Fuzzing Cluster
4. WebGPU & NPU Local Hardware Accelerators
5. Lean 4 Formal Mathematical Proof Synthesizer
6. Spatial 3D Neural Scene & WebXR Coder
7. SHA3 Vault Guard (NOT post-quantum -- see saleha/core/pqc_guard.py docstring)
8. Native Standalone Binary & LLVM Compiler
"""

import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer
from typing import Any, Dict

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler
from saleha.core.wasm_runner import wasm_engine
from saleha.core.visual_diff import visual_diff_engine
from saleha.core.p2p_swarm import p2p_engine
from saleha.core.webgpu_accelerator import webgpu_accelerator
from saleha.core.formal_verifier import formal_verifier
from saleha.core.spatial_coder import spatial_coder
from saleha.core.pqc_guard import sha3_vault_guard as pqc_guard
from saleha.core.native_compiler import native_compiler


class FutureEnginesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        web_server.set_auth_token("future-test-token")
        cls.token = "future-test-token"
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    # Some routes (e.g. /api/native/compile) invoke a subprocess with its own
    # 10s internal timeout server-side; the client timeout must exceed that
    # or a genuinely-still-running compile reads as a client-side failure.
    _HTTP_TIMEOUT = 15

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=self._HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            self.base + path,
            headers={"X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=self._HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # --- Phase 1: Wasm & Visual Diff ---
    def test_wasm_runner_manifest_and_worker(self) -> None:
        manifest = wasm_engine.generate_manifest(runtime="pyodide", packages=["numpy"])
        self.assertEqual(manifest.runtime, "pyodide")
        self.assertIn("numpy", manifest.packages)

        script = wasm_engine.generate_worker_script(manifest, code="print('Hello Wasm')")
        self.assertIn("loadPyodide", script)

        data = self._post("/api/wasm/manifest", {"runtime": "pyodide"})
        self.assertEqual(data["runtime"], "pyodide")

    def test_visual_diff_engine_comparison(self) -> None:
        base = "<html><body><h1>Title</h1><button>Click</button></body></html>"
        curr = "<html><body><h1>Title</h1><button>Click</button></body></html>"
        res = visual_diff_engine.compare_layouts(base, curr)
        self.assertTrue(res.is_match)
        self.assertGreaterEqual(res.similarity_score, 0.95)

        data = self._post("/api/vision/diff", {"base_html": base, "current_html": curr})
        self.assertTrue(data["is_match"])

    # --- Phase 2: P2P Swarm & WebGPU ---
    def test_p2p_swarm_distributed_fuzzing(self) -> None:
        res = p2p_engine.distribute_mutation_fuzzing("def safe(): return 1", total_mutations=200)
        self.assertTrue(res.consensus_achieved)
        self.assertGreaterEqual(res.nodes_participating, 1)

        data = self._post("/api/p2p/fuzz", {"code": "def run(): pass", "mutations": 100})
        self.assertTrue(data["consensus_achieved"])

    def test_webgpu_hardware_acceleration(self) -> None:
        # detect_hardware() cannot actually probe NPU/WebGPU capability from
        # a plain Python process (no vendor SDK or browser context), so it
        # honestly reports those fields as unmeasured (None) instead of a
        # fabricated True/number. Only OS/architecture are real detections.
        import platform

        rep = webgpu_accelerator.detect_hardware()
        self.assertEqual(rep.os_name, platform.system())
        self.assertEqual(rep.machine_arch, platform.machine())
        self.assertIsNone(rep.webgpu_supported)
        self.assertIsNone(rep.npu_detected)
        self.assertIsNone(rep.estimated_tokens_per_sec)
        self.assertTrue(rep.detection_note)

        shader = webgpu_accelerator.generate_wgsl_gemm_shader()
        self.assertIn("@compute", shader)

        data = self._get("/api/hardware/accel")
        self.assertIsNone(data["webgpu_supported"])
        self.assertIn("detection_note", data)

    # --- Phase 3: Formal Verification & Spatial UI ---
    def test_formal_lean4_verifier(self) -> None:
        # This is an unverified Lean 4 scaffold, not a checked proof: no Lean
        # toolchain runs, so lean_verified must stay False and the guarantee
        # text must say so rather than claiming correctness.
        res = formal_verifier.synthesize_proof_for_function("transfer_funds", "def transfer_funds(a, b): pass")
        self.assertTrue(res.is_valid_syntax)
        self.assertIn("Mathlib", res.lean4_code)
        self.assertFalse(res.lean_verified)
        self.assertIn("UNVERIFIED", res.correctness_guarantee)

        data = self._post("/api/formal/verify", {"function_name": "verify_vault", "code": "def verify(): pass"})
        self.assertTrue(data["lean_scaffold"]["is_valid_syntax"])
        self.assertFalse(data["lean_scaffold"]["lean_verified"])
        self.assertIn("smt_division_check", data)

    def test_spatial_3d_coder(self) -> None:
        res = spatial_coder.synthesize_spatial_ui("3D Crypto Dashboard")
        self.assertTrue(res.webxr_ready)
        self.assertIn("Canvas", res.code)

        data = self._post("/api/spatial/generate", {"prompt": "3D Metaverse Hub"})
        self.assertTrue(data["webxr_ready"])

    # --- Phase 4: SHA3 Vault Guard & Native Compiler ---
    def test_sha3_vault_guard_roundtrip(self) -> None:
        # pqc_guard does NOT implement CRYSTALS-Kyber or any NIST PQC
        # algorithm -- it is SHA3/SHAKE-256 symmetric hashing (see
        # saleha/core/pqc_guard.py docstring). This test verifies the real
        # property it has: a genuine encrypt/decrypt round-trip, and that
        # the algorithm label is honest about not being post-quantum.
        km = pqc_guard.generate_key_material()
        self.assertNotIn("Kyber", km.algorithm)
        self.assertNotIn("Dilithium", km.algorithm)

        enc = pqc_guard.encrypt_symmetric("TopSecretKey123", km.public_key_b64)
        self.assertNotIn("Kyber", enc.algorithm)
        dec = pqc_guard.decrypt_symmetric(enc, km.public_key_b64)
        self.assertEqual(dec, "TopSecretKey123")

        data = self._post("/api/pqc/encrypt", {"plaintext": "QuantumSafePassword"})
        self.assertNotIn("Kyber", data["algorithm"])
        self.assertIn("SHA3", data["algorithm"])

    def test_native_binary_compiler(self) -> None:
        # No fabricated success: this asserts on whatever the real compiler
        # subprocess result is on this machine, not a hardcoded True.
        c_code = "#include <stdio.h>\nint main() { printf(\"Saleha Native\"); return 0; }\n"
        res = native_compiler.compile_c_standalone(c_code, binary_name="test_native_app")
        if res.success:
            self.assertGreater(res.binary_size_bytes, 0)
            self.assertIsNotNone(res.compiler_used)
        else:
            self.assertEqual(res.binary_size_bytes, 0)
            self.assertIsNotNone(res.error_message)

        data = self._post("/api/native/compile", {"code": c_code, "binary_name": "api_test_app"})
        self.assertIn("success", data)
        self.assertIn("error_message", data)


if __name__ == "__main__":
    unittest.main()

