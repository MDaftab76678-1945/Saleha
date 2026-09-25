"""Regression tests for the pass-158 fixes in saleha/sandbox and the shared safety screen.

Each case below was measured passing the old screen/auditor, or crashing the
old driver, before the fix.
"""

import asyncio
import http.server
import json
import threading
import unittest
from typing import Any, Dict
from unittest import mock

from saleha.core.harness.code_executor import CodeExecutor
from saleha.core.ollama_endpoint import normalize_ollama_url
from saleha.core.safety_patterns import check_dangerous
from saleha.sandbox.ast_security_verifier import ASTContractAuditor
from saleha.sandbox.local_llm_driver import LocalLLMDriver
from saleha.sandbox.v5_production_core import SwarmGenesisRegistry, task_key

BYPASSES = [
    "import ctypes.util",
    "__import__('ctypes')",
    "from os import system\nsystem('x')",
    "import os as o\no.system('x')",
    "import subprocess\nsubprocess.run(['rm', '-rf', '/'])",
    "import shutil\nshutil.rmtree('C:/')",
    "getattr(__import__('os'), 'system')('x')",
    "m = __import__('o' + 's')",
    "import builtins\nm = builtins.__import__('o' + 's')",
    "f = eval\nf('1+1')",
    "getattr(__builtins__, '__im' + 'port__')('os')",
    "x = ().__class__.__base__.__subclasses__()",
    "g = (lambda: 0).__globals__",
    "import asyncio\nasyncio.create_subprocess_shell('whoami')",
]

SAFE = [
    "import math\nprint(math.sqrt(4))",
    "from re import compile\npat = compile('a+')",
    "import json\nfrom dataclasses import dataclass\n",
    "m = __import__('math')",
    "def f(x):\n    return getattr(x, 'name', None)\n",
]


class SharedScreenTests(unittest.TestCase):
    def test_every_known_bypass_is_refused_by_auditor_and_executor_screen(self) -> None:
        for code in BYPASSES:
            with self.subTest(code=code):
                ok, errors = ASTContractAuditor.audit(code, require_assertions=False)
                self.assertFalse(ok)
                self.assertTrue(errors)
                self.assertIsNotNone(check_dangerous(code))

    def test_ordinary_code_is_not_refused(self) -> None:
        for code in SAFE:
            with self.subTest(code=code):
                self.assertEqual(ASTContractAuditor.audit(code, require_assertions=False), (True, []))
                self.assertIsNone(check_dangerous(code))

    def test_executor_no_longer_runs_concatenated_import(self) -> None:
        res = CodeExecutor(audit=False).execute("m = __import__('o' + 's')\nprint(m.name)")
        self.assertTrue(res.blocked)
        self.assertIn("__import__", res.block_reason or "")

    def test_audit_of_non_text_fails_with_reason(self) -> None:
        ok, errors = ASTContractAuditor.audit(None)  # type: ignore[arg-type]
        self.assertFalse(ok)
        self.assertIn("NoneType", errors[0])

    def test_blocked_dynamic_import_reported_once(self) -> None:
        _, errors = ASTContractAuditor.audit("__import__('ctypes')", require_assertions=False)
        self.assertEqual(len(errors), 1, errors)


class _FakeOllama(http.server.BaseHTTPRequestHandler):
    reply: Dict[str, Any] = {}
    status = 200

    def do_POST(self) -> None:
        # Drain the request first: replying with unread data in the socket
        # makes Windows reset the connection, which the driver then (rightly)
        # reports as a transport failure -- a flaky test, not a driver bug.
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.dumps(self.reply).encode()
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - parent's name
        pass


class LocalLLMDriverTests(unittest.TestCase):
    def _serve(self, reply: Dict[str, Any], status: int = 200) -> str:
        handler = type("H", (_FakeOllama,), {"reply": reply, "status": status})
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def _generate(self, url: str, json_mode: bool = True) -> Dict[str, Any]:
        driver = LocalLLMDriver(ollama_url=url, vllm_url="http://127.0.0.1:9/v1")
        return asyncio.run(driver.generate_structured("hi", json_mode=json_mode))

    def test_non_json_output_is_an_error_not_an_exception(self) -> None:
        res = self._generate(self._serve({"response": "Sure! here is code"}))
        self.assertIn("not valid JSON", res["error"])

    def test_missing_response_field_is_an_error_not_empty_success(self) -> None:
        res = self._generate(self._serve({"done": True}))
        self.assertIn("error", res)

    def test_json_that_is_not_an_object_is_an_error(self) -> None:
        res = self._generate(self._serve({"response": "[1, 2]"}))
        self.assertIn("not an object", res["error"])

    def test_model_not_found_is_reported_with_ollama_reason(self) -> None:
        res = self._generate(self._serve({"error": "model 'x' not found"}, status=404))
        self.assertIn("HTTP 404", res["error"])
        self.assertIn("not found", res["error"])

    def test_good_json_passes_through(self) -> None:
        res = self._generate(self._serve({"response": '{"code": "x = 1"}'}))
        self.assertEqual(res, {"code": "x = 1"})

    def test_ollama_host_is_honoured_and_normalised(self) -> None:
        with mock.patch.dict("os.environ", {"OLLAMA_HOST": "0.0.0.0:11434", "SALEHA_OLLAMA_URL": ""}):
            self.assertEqual(LocalLLMDriver().ollama_url, "http://127.0.0.1:11434")


class OllamaEndpointTests(unittest.TestCase):
    def test_normalisation(self) -> None:
        cases = {
            "": "http://127.0.0.1:11434",
            "0.0.0.0:11434": "http://127.0.0.1:11434",
            "0.0.0.0": "http://127.0.0.1:11434",
            "http://localhost:11434/": "http://127.0.0.1:11434",
            "https://gpu-box:11434": "https://gpu-box:11434",
            "gpu-box": "http://gpu-box:11434",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_ollama_url(raw), expected)


class V5CoreTests(unittest.TestCase):
    def test_task_key_is_stable_across_processes(self) -> None:
        import subprocess
        import sys
        code = "from saleha.sandbox.v5_production_core import task_key; print(task_key('same task'))"
        other = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                               encoding="utf-8", timeout=60)
        self.assertEqual(other.stdout.strip(), task_key("same task"))

    def test_domain_cannot_escape_specs_dir(self) -> None:
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            reg = SwarmGenesisRegistry(specs_dir=tmp)
            path = reg.spec_path("../../evil")
            self.assertEqual(path.parent, Path(tmp))
            self.assertFalse(reg.agent_exists("go"))


if __name__ == "__main__":
    unittest.main()
