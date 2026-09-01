"""
Unit and integration tests for Phase 2: Live TUI Dashboard, Sandboxed MCP Client, P2P Mesh, and Web Studio API.
"""

import os
import shutil
import tempfile
import pytest

from saleha.cli.salehatop import SalehaTopDashboard
from saleha.core.sandboxed_mcp_client import SandboxedMCPClient, DiscoveredMCPTool
from saleha.core.p2p_mesh import P2PMeshNode, MeshNodeHeartbeat


class TestSalehaTopDashboard:
    def setup_method(self):
        self.dash = SalehaTopDashboard()

    def test_dashboard_layout_renders_without_exceptions(self):
        layout = self.dash.make_layout()
        assert layout is not None
        assert layout.get("header") is not None
        assert layout.get("main") is not None
        assert layout.get("footer") is not None

    def test_hardware_panel_generation(self):
        panel = self.dash.generate_hardware_panel()
        assert panel is not None
        assert "RAM Usage" in str(panel.renderable)

    def test_agent_matrix_grid_generation(self):
        panel = self.dash.generate_agents_grid()
        assert panel is not None

    def test_departments_table_generation(self):
        table = self.dash.generate_departments_table()
        assert table is not None
        assert len(table.rows) == 10


class TestSandboxedMCPClient:
    def setup_method(self):
        self.client = SandboxedMCPClient()

    def test_default_tools_registered(self):
        tools = self.client.list_tools()
        assert len(tools) >= 3
        tool_names = [t.name for t in tools]
        assert "mcp__fs_read_file" in tool_names
        assert "mcp__git_create_commit" in tool_names
        assert "mcp__sql_execute_query" in tool_names

    def test_safe_tool_execution(self):
        res = self.client.execute_tool("mcp__fs_read_file", {"path": "src/main.py"})
        assert res.success is True
        assert res.is_blocked is False
        assert res.output["status"] == "success"

    def test_malicious_rm_rf_payload_blocked(self):
        res = self.client.execute_tool("mcp__fs_read_file", {"path": "/etc/shadow; rm -rf /"})
        assert res.success is False
        assert res.is_blocked is True
        assert "GAMMA_SECURITY_ALERT" in res.security_reason
        assert "Recursive deletion" in res.security_reason or "credential" in res.security_reason

    def test_unauthorized_credential_access_blocked(self):
        res = self.client.execute_tool("mcp__fs_read_file", {"path": "/etc/passwd"})
        assert res.success is False
        assert res.is_blocked is True
        assert "credential path access" in res.security_reason


class TestP2PMeshNode:
    def setup_method(self):
        self.node_a = P2PMeshNode(node_id="Node-Alpha-Laptop", hosted_depts=(1, 5))
        self.node_b = P2PMeshNode(node_id="Node-Beta-Termux", hosted_depts=(6, 10))
        self.node_a.start()
        self.node_b.start()

    def teardown_method(self):
        self.node_a.stop()
        self.node_b.stop()

    def test_mesh_node_initialization(self):
        status = self.node_a.get_mesh_status()
        assert status["local_node"] == "Node-Alpha-Laptop"
        assert "[1 - 5]" in status["hosted_departments"]

    def test_peer_registration_and_remote_offloading(self):
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
