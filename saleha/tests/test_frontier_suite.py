"""Unit and Integration Test Suite for Saleha v3.2.0 Frontier Suite."""

from unittest.mock import MagicMock

from saleha.agents.chaos_resilience import (
    ChaosResilienceAgent,
    chaos_resilience,
)
from saleha.agents.screen_copilot import (
    ScreenCopilotAgent,
    screen_copilot,
)
from saleha.cli.chat_session import SwarmChatSession
from saleha.core.mcp_server import SalehaMCPServer
from saleha.core.swarm.swarm_cluster_node import SwarmClusterNode


class TestSalehaMCPServer:
    def test_list_tools(self) -> None:
        server = SalehaMCPServer()
        tools = server.list_tools()
        assert len(tools) >= 5
        names = [t["name"] for t in tools]
        assert "execute_swarm_dag" in names
        assert "validate_ast_code" in names
        assert "run_container_sandbox" in names

    def test_call_tool_ast(self) -> None:
        server = SalehaMCPServer()
        res = server.call_tool("validate_ast_code", {"code": "def valid(): return 1"})
        assert res["isError"] is False
        assert "AST Valid: True" in res["content"][0]["text"]

    def test_handle_jsonrpc_request(self) -> None:
        server = SalehaMCPServer()
        req = {"jsonrpc": "2.0", "id": 101, "method": "tools/list", "params": {}}
        res = server.handle_jsonrpc_request(req)
        assert res["jsonrpc"] == "2.0"
        assert res["id"] == 101
        assert "tools" in res["result"]

    def test_call_tool_execute_swarm_dag_does_not_fabricate_success(self) -> None:
        # A prior version of execute_swarm_dag returned a hardcoded
        # "Executed 27-Agent Pipeline ... Status: 100% Invariants Verified"
        # regardless of input, with zero agents actually invoked. It now
        # honestly reports that this tool is not wired to a bounded-time
        # synchronous call instead of fabricating a result.
        server = SalehaMCPServer()
        res = server.call_tool("execute_swarm_dag", {"goal": "build a thing"})
        assert res["isError"] is True
        assert "100%" not in res["content"][0]["text"]
        assert "Invariants Verified" not in res["content"][0]["text"]


class TestScreenCopilotAgent:
    def test_screen_copilot_execution(self) -> None:
        agent = ScreenCopilotAgent()
        res = agent.execute("Fix mobile flex wrapping and low contrast buttons")
        assert res.success is True
        assert "ScreenCopilotAgent" in res.content
        assert "Remediation Code & React JSX Patch" in res.content

    def test_inspect_screen_and_fix(self) -> None:
        result = screen_copilot.inspect_screen_and_fix("Navbar mobile breakpoint")
        assert len(result.detected_glitches) >= 2
        assert "RemediatedCard" in result.remediation_code_diff
        assert result.contrast_ratio_wcag_passed is True


class TestSwarmClusterNode:
    def test_register_peer_and_status(self) -> None:
        cluster = SwarmClusterNode(node_id="master-01")
        peer = cluster.register_peer("192.168.1.50", port=8765, cpu_cores=16, ram_gb=32.0)
        assert peer.ip_address == "192.168.1.50"
        status = cluster.get_cluster_status()
        assert status["total_nodes"] == 2
        assert status["total_cluster_cores"] == 24

    def test_dispatch_job(self) -> None:
        cluster = SwarmClusterNode()
        res = cluster.dispatch_job("test_suite", "pytest saleha/tests/")
        assert res.success is True
        assert "job-" in res.job_id


class TestChaosResilienceAgent:
    def test_chaos_agent_execution(self) -> None:
        agent = ChaosResilienceAgent()
        res = agent.execute("Auth Token Verification Service")
        assert res.success is True
        assert "ChaosResilienceAgent" in res.content
        assert "not measured" in res.content

    def test_run_chaos_test_claims_no_measurement(self) -> None:
        # This used to assert `resilience_score_pct >= 99.0` -- pinning a
        # hardcoded 99.98 that no experiment produced.
        result = chaos_resilience.run_chaos_test("Redis Cache Backend")
        assert "CircuitBreakerOpenException" in result.circuit_breaker_patch
        assert result.resilience_score_pct is None
        assert result.measured is False

    def test_circuit_breaker_template_actually_works(self) -> None:
        # Run the template for real, in the sandboxed test runner.
        from saleha.core.harness.test_runner import TestRunner
        template = chaos_resilience.run_chaos_test("svc").circuit_breaker_patch
        tests = (
            "import unittest\n"
            "class TestBreaker(unittest.TestCase):\n"
            "    def test_opens_after_max_failures(self):\n"
            "        calls = []\n"
            "        @resilient_circuit_breaker(max_failures=2, reset_timeout_sec=60)\n"
            "        def flaky():\n"
            "            calls.append(1)\n"
            "            raise ValueError('down')\n"
            "        for _ in range(2):\n"
            "            with self.assertRaises(ValueError):\n"
            "                flaky()\n"
            "        with self.assertRaises(CircuitBreakerOpenException):\n"
            "            flaky()\n"
            "        self.assertEqual(len(calls), 2)\n"
        )
        run = TestRunner().run_suite(template, test_code=tests, timeout=15)
        assert run.passed, run.failure_report()
        assert run.ran == 1


class TestSwarmChatSessionFrontierCommands:
    def test_process_frontier_commands(self) -> None:
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)
        assert session.process_command("/mcp status") is True
        assert session.process_command("/screen-inspect Broken Mobile Navbar") is True
        assert session.process_command("/cluster status") is True
        assert session.process_command("/chaos-test Redis Cluster") is True
