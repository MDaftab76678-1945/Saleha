"""
Unit and integration tests for Gamma Sandbox, Swarm Topology, Tri-Tier Memory, and DooM Workspace Engine.
"""

import os
import shutil
import tempfile
import pytest

from saleha.core.gamma_critic_sandbox import GammaSandboxEngine, GammaASTInspector
from saleha.core.saleha_swarm_topology import SalehaSwarmTopology, AgentRole, SwarmDepartment
from saleha.core.tri_tier_memory import TriTierMemoryEngine
from saleha.core.doom_workspace_engine import DoomWorkspaceEngine


class TestGammaCriticSandbox:
    def setup_method(self):
        self.engine = GammaSandboxEngine()

    def test_clean_python_code_passes(self):
        code = """
def calculate(a, b):
    if b != 0:
        return a / b
    return 0
"""
        report = self.engine.inspect_and_verify(code, language="python")
        assert report.passed is True
        assert len(report.violations) == 0

    def test_division_by_zero_literal_caught(self):
        code = """
def bad_divide():
    return 100 / 0
"""
        report = self.engine.inspect_and_verify(code, language="python")
        assert report.passed is False
        assert any(v.rule_id == "GAMMA_DIV_BY_ZERO" for v in report.violations)
        assert "[CRITIC_FEEDBACK_SIGNAL]" in report.feedback_signal

    def test_division_by_zero_variable_caught(self):
        code = """
divisor = 0
result = 500 / divisor
"""
        report = self.engine.inspect_and_verify(code, language="python")
        assert report.passed is False
        assert any("GAMMA_DIV_BY_ZERO" in v.rule_id for v in report.violations)

    def test_unclosed_resource_leak_caught(self):
        code = """
def leaky_file_read():
    f = open("test.txt", "r")
    data = f.read()
    return data
"""
        report = self.engine.inspect_and_verify(code, language="python")
        assert report.passed is False
        assert any(v.rule_id == "GAMMA_RESOURCE_LEAK" for v in report.violations)

    def test_c_polyglot_heuristics(self):
        c_code = """
int* ptr = malloc(128);
int result = 500 / 0;
"""
        report = self.engine.inspect_and_verify(c_code, language="c")
        assert report.passed is False
        assert any(v.rule_id == "GAMMA_DIV_BY_ZERO" for v in report.violations)
        assert any(v.rule_id == "GAMMA_MEMORY_LEAK" for v in report.violations)


class TestSalehaSwarmTopology:
    def setup_method(self):
        self.swarm = SalehaSwarmTopology()

    def test_topology_initialization(self):
        assert len(self.swarm.agents) == 250
        assert len(self.swarm.mailboxes) == 250
        
        # Verify 1:1 Shadow binding
        agent_5 = self.swarm.agents[5]
        assert agent_5.private_model_id == 255

    def test_fast_path_routing_low_complexity(self):
        prompt = "Fix buffer alignment in kernel driver"
        agent, is_fast_path, experts = self.swarm.route_task(prompt, complexity_score=10)
        assert is_fast_path is True
        assert len(experts) == 0  # No global swarm search needed
        assert agent.role == AgentRole.SYSTEMS_KERNEL

    def test_swarm_escalation_high_complexity(self):
        prompt = "Design distributed fault-tolerant crypto ledger"
        agent, is_fast_path, experts = self.swarm.route_task(prompt, complexity_score=85)
        assert is_fast_path is False
        assert len(experts) == 4  # Attached Top-4 swarm experts

    def test_lock_free_mailbox_delegation(self):
        success = self.swarm.delegate_subtask(
            from_agent_id=5,
            to_agent_id=110,
            task_id=9001,
            payload="audit_memory_safety",
        )
        assert success is True
        
        msg = self.swarm.poll_subtask(110)
        assert msg is not None
        assert msg.task_id == 9001
        assert msg.sender_agent_id == 5
        assert msg.payload == "audit_memory_safety"


class TestTriTierMemory:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mem = TriTierMemoryEngine(base_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_working_memory_ring(self):
        self.mem.working.append("Prompt 1", "Resp 1")
        self.mem.working.append("Prompt 2", "Resp 2")
        context = self.mem.working.get_recent_context(limit=2)
        assert len(context) == 2
        assert context[0].user_prompt == "Prompt 1"

    def test_episodic_memory_persistence(self):
        self.mem.episodic.record(
            agent_id=5,
            summary="Zero-Copy Kernel Ring Buffer Implemented",
            status="VERIFIED_SAFE",
            tags=["kernel", "af_xdp"],
        )
        results = self.mem.episodic.search("Kernel Ring")
        assert len(results) >= 1
        assert results[0].status == "VERIFIED_SAFE"

    def test_semantic_knowledge_graph(self):
        self.mem.semantic.insert_fact(
            subject="KernelDriver",
            predicate="implements_protocol",
            obj="AF_XDP_ZeroCopy",
        )
        facts = self.mem.semantic.query_relations("KernelDriver")
        assert len(facts) >= 1
        assert facts[0].object == "AF_XDP_ZeroCopy"

    def test_unified_recall(self):
        self.mem.working.append("Fix buffer", "Fixed")
        self.mem.episodic.record(5, "Buffer overflow repaired", "PASSED", ["buffer"])
        self.mem.semantic.insert_fact("Buffer", "type", "CircularQueue")

        ctx = self.mem.recall_context("Buffer")
        assert len(ctx["working_memory"]) >= 1
        assert len(ctx["episodic_history"]) >= 1
        assert len(ctx["semantic_facts"]) >= 1


class TestDoomWorkspaceEngine:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = DoomWorkspaceEngine(
            workspace_dir=self.temp_dir,
            auto_heal=True,
            auto_git_commit=False,
        )

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_file_passes_audit(self):
        fpath = os.path.join(self.temp_dir, "clean_module.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\n")

        res = self.engine.process_file_change(fpath)
        assert res.gamma_passed is True
        assert res.repaired is False

    def test_auto_heal_division_by_zero(self):
        fpath = os.path.join(self.temp_dir, "buggy_calc.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("divisor = 0\nres = 500 / divisor\n")

        res = self.engine.process_file_change(fpath)
        assert res.gamma_passed is True
        assert res.repaired is True
        
        # Verify content was patched
        with open(fpath, "r", encoding="utf-8") as f:
            patched_code = f.read()
        assert "divisor = 1" in patched_code

