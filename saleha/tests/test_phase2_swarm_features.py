"""
Unit and integration tests for Phase 2: Live TUI Dashboard, Sandboxed MCP Client, P2P Mesh, and Web Studio API.
"""

import os
import shutil
import tempfile
import pytest

from saleha.cli.salehatop import SalehaTopDashboard
from saleha.core.sandboxed_mcp_client import SandboxedMCPClient, DiscoveredMCPTool
from saleha.core.swarm.p2p_mesh import P2PMeshNode, MeshNodeHeartbeat


class TestSalehaTopDashboard:
    def setup_method(self) -> None:
        self.dash = SalehaTopDashboard()

    def test_dashboard_layout_renders_without_exceptions(self) -> None:
        layout = self.dash.make_layout()
        assert layout is not None
        assert layout.get("header") is not None
        assert layout.get("main") is not None
        assert layout.get("footer") is not None

    def test_hardware_panel_reports_measured_values(self) -> None:
        import psutil

        text = str(self.dash.generate_hardware_panel().renderable)
        assert "RAM Usage" in text
        # The old panel printed a formula of the tick counter ("2,200 MB Hard Cap").
        assert f"/ {psutil.virtual_memory().total / 1024 ** 3:.1f} GB" in text
        assert "Jobs/sec" not in text and "< 15 ns" not in text

    def test_bus_activity_counts_real_events(self) -> None:
        from saleha.core.swarm.agent_message_bus import AgentEvent, message_bus

        message_bus.clear()
        empty = self.dash.generate_bus_activity_table()
        assert empty.columns[0]._cells == ["(no events)"]
        message_bus.publish(AgentEvent(event_type="probe.event", sender_agent="ProbeAgent"))
        try:
            table = self.dash.generate_bus_activity_table()
            assert "probe.event" in table.columns[0]._cells
            assert "ProbeAgent" in table.columns[1]._cells
        finally:
            message_bus.clear()

    def test_event_log_never_invents_events(self) -> None:
        from saleha.core.swarm.agent_message_bus import message_bus

        message_bus.clear()
        for tick in range(6):
            self.dash.tick = tick
            body = str(self.dash.generate_event_log().renderable)
            assert "No message-bus events" in body
            assert "CWEs" not in body and "pytest assertions" not in body


class TestSandboxedMCPClient:
    def setup_method(self) -> None:
        self.client = SandboxedMCPClient()

    def test_default_tools_registered(self) -> None:
        tools = self.client.list_tools()
        assert len(tools) >= 3
        tool_names = [t.name for t in tools]
        assert "mcp__fs_read_file" in tool_names
        assert "mcp__git_create_commit" in tool_names
        assert "mcp__sql_execute_query" in tool_names

    def test_safe_tool_execution(self) -> None:
        res = self.client.execute_tool("mcp__fs_read_file", {"path": "src/main.py"})
        assert res.success is True
        assert res.is_blocked is False
        assert res.output["status"] == "success"

    def test_malicious_rm_rf_payload_blocked(self) -> None:
        res = self.client.execute_tool("mcp__fs_read_file", {"path": "/etc/shadow; rm -rf /"})
        assert res.success is False
        assert res.is_blocked is True
        reason = res.security_reason
        assert reason is not None
        assert "GAMMA_SECURITY_ALERT" in reason
        assert "Recursive deletion" in reason or "credential" in reason

    def test_unauthorized_credential_access_blocked(self) -> None:
        res = self.client.execute_tool("mcp__fs_read_file", {"path": "/etc/passwd"})
        assert res.success is False
        assert res.is_blocked is True
        reason = res.security_reason
        assert reason is not None
        assert "credential path access" in reason


class TestP2PMeshNode:
    def setup_method(self) -> None:
        self.node_a = P2PMeshNode(node_id="Node-Alpha-Laptop", hosted_depts=(1, 5))
        self.node_b = P2PMeshNode(node_id="Node-Beta-Termux", hosted_depts=(6, 10))
        self.node_a.start()
        self.node_b.start()

    def teardown_method(self) -> None:
        self.node_a.stop()
        self.node_b.stop()

    def test_mesh_node_initialization(self) -> None:
        status = self.node_a.get_mesh_status()
        assert status["local_node"] == "Node-Alpha-Laptop"
        assert "[1 - 5]" in status["hosted_departments"]

    def test_peer_registration_and_remote_offloading(self) -> None:
        # Register Node B as a peer on Node A
        self.node_a.register_peer(MeshNodeHeartbeat(
            node_id="Node-Beta-Termux",
            host_ip="192.168.1.50",
            hosted_dept_start=6,
            hosted_dept_end=10,
        ))

        # Offload task meant for Department #7 (hosted by Node B)
        offload_res = self.node_a.offload_task_to_peer(
            task_id=9901,
            sender_agent_id=5,
            target_dept=7,
            code="verify_seccomp()",
        )

        assert offload_res["status"] == "OFFLOADED_SUCCESS"
        assert offload_res["assigned_destination_node"] == "Node-Beta-Termux"
        assert offload_res["target_department"] == 7
