"""Saleha Core: Autonomous Sandbox Virtual Mock Synthesizer.

Provides zero-dependency in-memory mock virtualization for isolated sandboxes:
1. Synthesizes deterministic stubs for external network services (HTTP, Boto3, Stripe, Redis).
2. Intercepts external calls in network-disabled Win32 Job Object environments.
3. Injects AST/prelude stubs so unit tests exercise edge cases and happy paths offline.
4. Preserves security invariant: zero actual network socket creation.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


VIRTUAL_MOCK_PRELUDE = """# --- AUTONOMOUS VIRTUAL MOCK HARNESS (NETWORK-ISOLATED) ---
import sys
import types

# 1. Virtual 'requests' module
if "requests" not in sys.modules:
    class _MockResponse:
        def __init__(self, data=None, status_code=200, text="OK"):
            self._data = data or {"status": "success", "id": "mock_123", "data": []}
            self.status_code = status_code
            self.text = text
            self.ok = 200 <= status_code < 300

        def json(self):
            return self._data

        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError(f"HTTP Error {self.status_code}: {self.text}")

    class _MockRequests(types.ModuleType):
        Response = _MockResponse

        @staticmethod
        def get(url, *args, **kwargs):
            return _MockResponse({"url": url, "method": "GET", "status": "ok"})

        @staticmethod
        def post(url, *args, **kwargs):
            payload = kwargs.get("json", kwargs.get("data", {}))
            return _MockResponse({"url": url, "method": "POST", "payload": payload})

        @staticmethod
        def put(url, *args, **kwargs):
            return _MockResponse({"url": url, "method": "PUT"})

        @staticmethod
        def delete(url, *args, **kwargs):
            return _MockResponse({"url": url, "method": "DELETE", "deleted": True})

    sys.modules["requests"] = _MockRequests("requests")

# 2. Virtual 'redis' module
if "redis" not in sys.modules:
    class _MockRedis:
        def __init__(self, *args, **kwargs):
            self._store = {}

        def get(self, key):
            val = self._store.get(str(key))
            return val.encode("utf-8") if isinstance(val, str) else val

        def set(self, key, value, *args, **kwargs):
            self._store[str(key)] = value
            return True

        def delete(self, key):
            return 1 if self._store.pop(str(key), None) is not None else 0

        def exists(self, key):
            return 1 if str(key) in self._store else 0

    class _MockRedisModule(types.ModuleType):
        Redis = _MockRedis
        StrictRedis = _MockRedis

    sys.modules["redis"] = _MockRedisModule("redis")

# 3. Virtual 'boto3' (AWS SDK)
if "boto3" not in sys.modules:
    class _MockS3Client:
        def list_objects_v2(self, Bucket="", **kwargs):
            return {"Contents": [{"Key": "sample.csv", "Size": 1024}]}

        def get_object(self, Bucket="", Key=""):
            class _Body:
                def read(self):
                    return b"mock,csv,data\\n1,2,3"
            return {"Body": _Body(), "ContentLength": 18}

        def put_object(self, Bucket="", Key="", Body=b"", **kwargs):
            return {"ETag": '"mock_etag_123"', "VersionId": "v1"}

    class _MockBoto3(types.ModuleType):
        @staticmethod
        def client(service_name, *args, **kwargs):
            if service_name == "s3":
                return _MockS3Client()
            return types.SimpleNamespace()

    sys.modules["boto3"] = _MockBoto3("boto3")

# 4. Virtual 'stripe' module
if "stripe" not in sys.modules:
    class _MockStripe(types.ModuleType):
        api_key = "mock_key"

        class Charge:
            @staticmethod
            def create(**kwargs):
                return {
                    "id": "ch_mock_123456",
                    "status": "succeeded",
                    "amount": kwargs.get("amount", 1000),
                    "currency": kwargs.get("currency", "usd"),
                    "paid": True,
                }

        class PaymentIntent:
            @staticmethod
            def create(**kwargs):
                return {
                    "id": "pi_mock_123456",
                    "status": "succeeded",
                    "amount": kwargs.get("amount", 1000),
                }

    sys.modules["stripe"] = _MockStripe("stripe")
# --- END AUTONOMOUS VIRTUAL MOCK HARNESS ---
"""


@dataclass
class MockContract:
    """Specification of an external dependency to virtualize in sandbox."""
    module_name: str
    target_functions: List[str]
    mock_responses: Dict[str, Any] = field(default_factory=dict)


class SandboxMockSynthesizer:
    """Synthesizes zero-dependency virtual mocks for network-isolated sandbox runs."""

    MOCKABLE_MODULES = {"requests", "urllib.request", "redis", "boto3", "stripe"}

    def __init__(self) -> None:
        self.registered_contracts: Dict[str, MockContract] = {}

    def detect_external_dependencies(self, source_code: str) -> Set[str]:
        """Scans code AST to detect imports of mockable external services."""
        external_found: Set[str] = set()
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base = alias.name.split(".")[0]
                        if base in self.MOCKABLE_MODULES:
                            external_found.add(base)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        base = node.module.split(".")[0]
                        if base in self.MOCKABLE_MODULES:
                            external_found.add(base)
        except Exception:
            pass
        return external_found

    def inject_virtual_mocks(self, source_code: str, force_inject: bool = False) -> str:
        """Prepends virtual mock prelude if external dependencies are detected."""
        deps = self.detect_external_dependencies(source_code)
        if deps or force_inject:
            return f"{VIRTUAL_MOCK_PRELUDE}\n\n{source_code}"
        return source_code

    def synthesize_custom_mock_module(
        self,
        module_name: str,
        class_name: str,
        methods: Dict[str, Any],
    ) -> str:
        """Dynamically generates a custom in-memory mock module snippet."""
        method_defs: List[str] = []
        for method_name, ret_value in methods.items():
            ret_repr = repr(ret_value)
            method_defs.append(f"""        def {method_name}(self, *args, **kwargs):
            return {ret_repr}""")

        methods_code = "\n".join(method_defs)
        return f"""
import sys, types
if "{module_name}" not in sys.modules:
    class {class_name}:
{methods_code}
    _mod = types.ModuleType("{module_name}")
    _mod.{class_name} = {class_name}
    sys.modules["{module_name}"] = _mod
"""
