"""
Unit and integration tests for Phase 3: Multimodal Ingress, Wasm Micro-Plugin Runtime, and Hardware Watchdog.
"""

import time
import pytest

from saleha.core.saleha_multimodal import SalehaMultimodalHub
from saleha.core.saleha_wasm_runtime import SalehaWasmRuntime, WASIPermission
from saleha.core.saleha_watchdog import SalehaHardwareWatchdog


class TestSalehaMultimodalHub:
    def setup_method(self):
        self.hub = SalehaMultimodalHub()

    def test_multimodal_fusion_generation(self):
        payload = self.hub.fuse_inputs(
            voice_command="Saleha, fix the pointer arithmetic bug",
            window_title="VS Code - buffer_pool.c",
            screen_error="buffer_pool.c:42: Error: pointer out of bounds",
        )
        assert payload is not None
        assert payload.voice_intent == "Saleha, fix the pointer arithmetic bug"
        assert payload.active_window == "VS Code - buffer_pool.c"
        assert "pointer out of bounds" in payload.screen_error_context
        assert "<multimodal_payload>" in payload.fused_prompt
        assert payload.latency_ms >= 0.0


class TestSalehaWasmRuntime:
    def setup_method(self):
        self.runtime = SalehaWasmRuntime()

    def test_default_plugins_listed(self):
        plugins = self.runtime.list_plugins()
        assert len(plugins) >= 2
        names = [p["name"] for p in plugins]
        assert "crypto_tools.wasm" in names
        assert "ast_parser.wasm" in names

    def test_crypto_wasm_execution_with_gas(self):
        res = self.runtime.invoke_plugin(
            plugin_name="crypto_tools.wasm",
            func_name="rust_sha3_digest",
            input_payload="raw_block_data",
        )
        assert res.success is True
        assert res.is_blocked is False
        assert res.gas_used > 0
        assert res.output["algorithm"] == "SHA3-256"

    def test_ast_parser_wasm_execution(self):
        res = self.runtime.invoke_plugin(
            plugin_name="ast_parser.wasm",
            func_name="python_ast_validator",
            input_payload="def foo(): return 42",
        )
        assert res.success is True
        assert res.output["valid"] is True

    def test_network_permission_blocked_without_capability(self):
        res = self.runtime.invoke_plugin(
            plugin_name="crypto_tools.wasm",
            func_name="network_fetch",
            input_payload="http://remote.api",
            permissions=WASIPermission.READ_ONLY_FS,  # No network permission
        )
        assert res.success is False
        assert res.is_blocked is True
        assert "Network Socket Not Permitted" in res.security_reason


class TestSalehaHardwareWatchdog:
    def setup_method(self):
        self.dog = SalehaHardwareWatchdog(timeout_sec=0.05)  # 50ms timeout for fast tests

    def test_healthy_workers_registered_and_pinged(self):
        self.dog.register_worker(0, "Saleha-Agent-01")
        self.dog.register_worker(1, "Saleha-Agent-05")
        
        status = self.dog.get_status()
        assert status["total_monitored_workers"] == 2
        assert status["healthy_workers"] == 2
        assert status["quarantined_workers"] == 0

    def test_deadlock_detection_and_auto_respawn(self):
        self.dog.register_worker(0, "Rogue-Worker-Thread")
        
        # Simulate time passing without heartbeat ping
        time.sleep(0.06)
        
        events = self.dog.check_health()
        assert len(events) >= 1
        assert events[0]["event"] == "DEADLOCK_QUARANTINED_AND_RESPAWNED"
        assert events[0]["worker_name"] == "Rogue-Worker-Thread"
        assert events[0]["status"] == "HEALTH_RESTORED"
        
        # Health state should be restored after auto-respawn
        status = self.dog.get_status()
        assert status["healthy_workers"] == 1

