"""Unit and Integration Test Suite for Saleha v3.2.0 Frontier Suite."""

import pytest
from unittest.mock import MagicMock

from saleha.core.mcp_server import (
    SalehaMCPServer,
    saleha_mcp_server,
)
from saleha.agents.screen_copilot import (
    ScreenCopilotAgent,
    ScreenInspectionResult,
    screen_copilot,
)
from saleha.core.swarm_cluster_node import (
    SwarmClusterNode,
    ClusterPeer,
    swarm_cluster,
)
from saleha.agents.chaos_resilience import (
    ChaosResilienceAgent,
    ChaosExperimentResult,
    chaos_resilience,
)
from saleha.cli.chat_session import SwarmChatSession


class TestSalehaMCPServer:
    def test_list_tools(self):
        server = SalehaMCPServer()
        tools = server.list_tools()
        assert len(tools) >= 5
        names = [t["name"] for t in tools]
        assert "execute_swarm_dag" in names
        assert "validate_ast_code" in names
        assert "run_container_sandbox" in names

    def test_call_tool_ast(self):
        server = SalehaMCPServer()
        res = server.call_tool("validate_ast_code", {"code": "def valid(): return 1"})
        assert res["isError"] is False
        assert "AST Valid: True" in res["content"][0]["text"]

    def test_handle_jsonrpc_request(self):
        server = SalehaMCPServer()
        req = {"jsonrpc": "2.0", "id": 101, "method": "tools/list", "params": {}}
        res = server.handle_jsonrpc_request(req)
        assert res["jsonrpc"] == "2.0"
        assert res["id"] == 101
        assert "tools" in res["result"]


class TestScreenCopilotAgent:
    def test_screen_copilot_execution(self):
        agent = ScreenCopilotAgent()
        res = agent.execute("Fix mobile flex wrapping and low contrast buttons")
        assert res.success is True
        assert "ScreenCopilotAgent" in res.content
        assert "Remediation Code & React JSX Patch" in res.content

    def test_inspect_screen_and_fix(self):
        result = screen_copilot.inspect_screen_and_fix("Navbar mobile breakpoint")
        assert len(result.detected_glitches) >= 2
        assert "RemediatedCard" in result.remediation_code_diff
        assert result.contrast_ratio_wcag_passed is True


class TestSwarmClusterNode:
    def test_register_peer_and_status(self):
        cluster = SwarmClusterNode(node_id="master-01")
        peer = cluster.register_peer("192.168.1.50", port=8765, cpu_cores=16, ram_gb=32.0)
        assert peer.ip_address == "192.168.1.50"
        status = cluster.get_cluster_status()
        assert status["total_nodes"] == 2
        assert status["total_cluster_cores"] == 24

    def test_dispatch_job(self):
        cluster = SwarmClusterNode()
        res = cluster.dispatch_job("test_suite", "pytest saleha/tests/")
        assert res.success is True
        assert "job-" in res.job_id


class TestChaosResilienceAgent:
    def test_chaos_agent_execution(self):
        agent = ChaosResilienceAgent()
        res = agent.execute("Auth Token Verification Service")
        assert res.success is True
        assert "ChaosResilienceAgent" in res.content
        assert "Synthesized Self-Healing Circuit Breaker" in res.content

    def test_run_chaos_test(self):
        result = chaos_resilience.run_chaos_test("Redis Cache Backend")
        assert "CircuitBreakerOpenException" in result.circuit_breaker_patch
        assert result.resilience_score_pct >= 99.0


class TestSwarmChatSessionFrontierCommands:
    def test_process_frontier_commands(self):
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)
        assert session.process_command("/mcp status") is True
        assert session.process_command("/screen-inspect Broken Mobile Navbar") is True
        assert session.process_command("/cluster status") is True
        assert session.process_command("/chaos-test Redis Cluster") is True
