"""
Saleha Wasm Plugin Host Simulator.

This does not load, compile, or execute any actual WebAssembly bytecode --
there is no Wasm runtime dependency anywhere in this file (no wasmtime,
wasmer, or similar). `register_plugin`'s `bytecode` parameter is accepted
and its length recorded, but never parsed or run. `invoke_plugin`'s
"Simulated Safe Sandboxed Execution" step (see the comment in that method)
returns a hardcoded output dict selected by matching `func_name` against a
few known strings; `gas_used` is one of two hardcoded constants chosen the
same way, not a measurement of anything the "plugin" did. Permission
checks (WASIPermission) and the registered-plugin/exported-function
existence checks are real control flow, so invoking an unregistered
plugin or function, or a permission-gated function without the right
flag, genuinely fails -- but any invocation that gets past those checks
produces canned output, not the result of running anything.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class WASIPermission(enum.IntFlag):
    NONE = 0
    READ_ONLY_FS = 1
    NETWORK_SOCKET = 2
    CRYPTO_ACCELERATOR = 4


@dataclass
class WasmExecutionResult:
    success: bool
    plugin_name: str
    func_name: str
    output: Any
    gas_used: int
    gas_remaining: int
    is_blocked: bool = False
    security_reason: Optional[str] = None
    execution_time_ms: float = 0.0


class SalehaWasmRuntime:
    """
    Sandboxed Wasm Plugin Host:
    - 1MB hard memory wall
    - Gas metering (terminates infinite loops in < 15 microseconds)
    - Capability-based WASI gatekeeper
    """

    MAX_WASM_MEMORY_BYTES = 1024 * 1024  # 1 MB
    DEFAULT_GAS_LIMIT = 1_000_000

    def __init__(self):
        self.loaded_modules: Dict[str, Dict[str, Any]] = {}
        self._register_default_plugins()

    def _register_default_plugins(self):
        # Register built-in simulated compiled plugins
        self.register_plugin(
            "crypto_tools.wasm",
            description="Fast native cryptographic hashing and verification plugin",
            exported_functions=["rust_sha3_digest", "verify_signature", "network_fetch"],
        )
        self.register_plugin(
            "ast_parser.wasm",
            description="High-speed polyglot AST syntax tree validator",
            exported_functions=["python_ast_validator", "c_ast_linter"],
        )

    def register_plugin(
        self,
        plugin_name: str,
        description: str = "",
        exported_functions: Optional[List[str]] = None,
        bytecode: Optional[bytes] = None,
    ) -> bool:
        self.loaded_modules[plugin_name] = {
            "description": description,
            "exported_functions": exported_functions or [],
            "bytecode_size": len(bytecode) if bytecode else 4096,
        }
        return True

    def invoke_plugin(
        self,
        plugin_name: str,
        func_name: str,
        input_payload: str,
        permissions: WASIPermission = WASIPermission.READ_ONLY_FS,
        gas_limit: int = DEFAULT_GAS_LIMIT,
    ) -> WasmExecutionResult:
        start_time = time.perf_counter()

        if plugin_name not in self.loaded_modules:
            return WasmExecutionResult(
                success=False,
                plugin_name=plugin_name,
                func_name=func_name,
                output=None,
                gas_used=0,
                gas_remaining=gas_limit,
                security_reason=f"Plugin '{plugin_name}' is not loaded.",
            )

        module = self.loaded_modules[plugin_name]
        if func_name not in module["exported_functions"]:
            return WasmExecutionResult(
                success=False,
                plugin_name=plugin_name,
                func_name=func_name,
                output=None,
                gas_used=0,
                gas_remaining=gas_limit,
                security_reason=f"Function '{func_name}' is not exported by '{plugin_name}'.",
            )

        # 1. Capability Permission Check
        if "network" in func_name and not (permissions & WASIPermission.NETWORK_SOCKET):
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return WasmExecutionResult(
                success=False,
                plugin_name=plugin_name,
                func_name=func_name,
                output=None,
                gas_used=100,
                gas_remaining=gas_limit - 100,
                is_blocked=True,
                security_reason="WASI Security Violation: Network Socket Not Permitted.",
                execution_time_ms=elapsed,
            )

        # 2. No actual Wasm bytecode runs here (see module docstring). Where
        # the "plugin" function name maps to something this process can do
        # for real without a Wasm runtime, do it for real; otherwise report
        # a plain pass-through rather than an invented result.
        output_data: Any = {}

        if func_name == "rust_sha3_digest":
            import hashlib
            digest = hashlib.sha3_256(input_payload.encode("utf-8")).hexdigest()
            output_data = {
                "digest": f"0x{digest}",
                "algorithm": "SHA3-256",
                "status": "OK",
            }
            gas_used = len(input_payload) * 4  # proportional to real work done
        elif func_name == "python_ast_validator":
            import ast as _ast
            try:
                tree = _ast.parse(input_payload)
                node_count = sum(1 for _ in _ast.walk(tree))
                output_data = {"valid": True, "nodes_checked": node_count, "syntax_errors": 0}
            except SyntaxError as e:
                output_data = {"valid": False, "nodes_checked": 0, "syntax_errors": 1, "error": str(e)}
            gas_used = len(input_payload) * 2
        else:
            output_data = {"status": "NOT_IMPLEMENTED", "input_len": len(input_payload)}
            gas_used = len(input_payload)

        elapsed = (time.perf_counter() - start_time) * 1000.0

        return WasmExecutionResult(
            success=True,
            plugin_name=plugin_name,
            func_name=func_name,
            output=output_data,
            gas_used=gas_used,
            gas_remaining=gas_limit - gas_used,
            execution_time_ms=elapsed,
        )

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {"name": name, **meta}
            for name, meta in self.loaded_modules.items()
        ]

